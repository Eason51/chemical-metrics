

from torch import nn
import torch
import torch.nn.functional as F
import math
from copy import deepcopy


from fastNLP import logger, Vocabulary
from fastNLP.embeddings import TokenEmbedding
from fastNLP.embeddings.utils import _construct_char_vocab_from_vocab, get_embeddings
from fastNLP.modules import ConditionalRandomField, allowed_transitions

MAX_SEQ_LEN = 1536


class RelativeEmbedding(nn.Module):
    def forward(self, input):
        """Input is expected to be of size [bsz x seqlen].
        """
        bsz, seq_len = input.size()
        max_pos = self.padding_idx + seq_len
        if max_pos > self.origin_shift:
            # recompute/expand embeddings if needed
            weights = self.get_embedding(
                max_pos * 2,
                self.embedding_dim,
                self.padding_idx,
            )
            weights = weights.to(self._float_tensor)
            del self.weights
            self.origin_shift = weights.size(0) // 2
            self.register_buffer('weights', weights)

        positions = torch.arange(-seq_len, seq_len).to(input.device).long() + self.origin_shift  # 2*seq_len
        embed = self.weights.index_select(0, positions.long()).detach()
        return embed


class RelativeSinusoidalPositionalEmbedding(RelativeEmbedding):
    """This module produces sinusoidal positional embeddings of any length.
    Padding symbols are ignored.
    """

    def __init__(self, embedding_dim, padding_idx, init_size=1536):
        """
        :param embedding_dim: 每个位置的dimension
        :param padding_idx:
        :param init_size:
        """
        super().__init__()
        self.embedding_dim = embedding_dim
        self.padding_idx = padding_idx
        assert init_size % 2 == 0
        weights = self.get_embedding(
            init_size + 1,
            embedding_dim,
            padding_idx,
        )
        self.register_buffer('weights', weights)
        self.register_buffer('_float_tensor', torch.FloatTensor(1))

    def get_embedding(self, num_embeddings, embedding_dim, padding_idx=None):
        """Build sinusoidal embeddings.
        This matches the implementation in tensor2tensor, but differs slightly
        from the description in Section 3.5 of "Attention Is All You Need".
        """
        half_dim = embedding_dim // 2
        emb = math.log(10000) / (half_dim - 1)
        emb = torch.exp(torch.arange(half_dim, dtype=torch.float) * -emb)
        emb = torch.arange(-num_embeddings // 2, num_embeddings // 2, dtype=torch.float).unsqueeze(1) * emb.unsqueeze(0)
        emb = torch.cat([torch.sin(emb), torch.cos(emb)], dim=1).view(num_embeddings, -1)
        if embedding_dim % 2 == 1:
            # zero pad
            emb = torch.cat([emb, torch.zeros(num_embeddings, 1)], dim=1)
        if padding_idx is not None:
            emb[padding_idx, :] = 0
        self.origin_shift = num_embeddings // 2 + 1
        return emb


class RelativeMultiHeadAttn(nn.Module):
    def __init__(self, d_model, n_head, dropout, r_w_bias=None, r_r_bias=None, scale=False):
        """
        :param int d_model:
        :param int n_head:
        :param dropout: 对attention map的dropout
        :param r_w_bias: n_head x head_dim or None, 如果为dim
        :param r_r_bias: n_head x head_dim or None,
        :param scale:
        :param rel_pos_embed:
        """
        super().__init__()
        self.qkv_linear = nn.Linear(d_model, d_model * 3, bias=False)
        self.n_head = n_head
        self.head_dim = d_model // n_head
        self.dropout_layer = nn.Dropout(dropout)

        self.pos_embed = RelativeSinusoidalPositionalEmbedding(d_model // n_head, 0, 1200)

        if scale:
            self.scale = math.sqrt(d_model // n_head)
        else:
            self.scale = 1

        if r_r_bias is None or r_w_bias is None:  # Biases are not shared
            self.r_r_bias = nn.Parameter(nn.init.xavier_normal_(torch.zeros(n_head, d_model // n_head)))
            self.r_w_bias = nn.Parameter(nn.init.xavier_normal_(torch.zeros(n_head, d_model // n_head)))
        else:
            self.r_r_bias = r_r_bias  # r_r_bias就是v
            self.r_w_bias = r_w_bias  # r_w_bias就是u

    def forward(self, x, mask):
        """
        :param x: batch_size x max_len x d_model
        :param mask: batch_size x max_len
        :return:
        """

        batch_size, max_len, d_model = x.size()
        pos_embed = self.pos_embed(mask)  # l x head_dim

        qkv = self.qkv_linear(x)  # batch_size x max_len x d_model3
        q, k, v = torch.chunk(qkv, chunks=3, dim=-1)
        q = q.view(batch_size, max_len, self.n_head, -1).transpose(1, 2)
        k = k.view(batch_size, max_len, self.n_head, -1).transpose(1, 2)
        v = v.view(batch_size, max_len, self.n_head, -1).transpose(1, 2)  # b x n x l x d

        rw_head_q = q + self.r_r_bias[:, None]
        AC = torch.einsum('bnqd,bnkd->bnqk', [rw_head_q, k])  # b x n x l x d, n是head

        D_ = torch.einsum('nd,ld->nl', self.r_w_bias, pos_embed)[None, :, None]  # head x 2max_len, 每个head对位置的bias
        B_ = torch.einsum('bnqd,ld->bnql', q, pos_embed)  # bsz x head  x max_len x 2max_len，每个query对每个shift的偏移
        E_ = torch.einsum('bnqd,ld->bnql', k, pos_embed)  # bsz x head x max_len x 2max_len, key对relative的bias
        BD = B_ + D_  # bsz x head x max_len x 2max_len, 要转换为bsz x head x max_len x max_len
        BDE = self._shift(BD) + self._transpose_shift(E_)
        attn = AC + BDE

        attn = attn / self.scale

        attn = attn.masked_fill(mask[:, None, None, :].eq(0), float('-inf'))

        attn = F.softmax(attn, dim=-1)
        attn = self.dropout_layer(attn)
        v = torch.matmul(attn, v).transpose(1, 2).reshape(batch_size, max_len, d_model)  # b x n x l x d

        return v

    def _shift(self, BD):
        """
        类似
        -3 -2 -1 0 1 2
        -3 -2 -1 0 1 2
        -3 -2 -1 0 1 2
        转换为
        0   1  2
        -1  0  1
        -2 -1  0
        :param BD: batch_size x n_head x max_len x 2max_len
        :return: batch_size x n_head x max_len x max_len
        """
        bsz, n_head, max_len, _ = BD.size()
        zero_pad = BD.new_zeros(bsz, n_head, max_len, 1)
        BD = torch.cat([BD, zero_pad], dim=-1).view(bsz, n_head, -1, max_len)  # bsz x n_head x (2max_len+1) x max_len
        BD = BD[:, :, :-1].view(bsz, n_head, max_len, -1)  # bsz x n_head x 2max_len x max_len
        BD = BD[:, :, :, max_len:]
        return BD

    def _transpose_shift(self, E):
        """
        类似
          -3   -2   -1   0   1   2
         -30  -20  -10  00  10  20
        -300 -200 -100 000 100 200
        转换为
          0  -10   -200
          1   00   -100
          2   10    000
        :param E: batch_size x n_head x max_len x 2max_len
        :return: batch_size x n_head x max_len x max_len
        """
        bsz, n_head, max_len, _ = E.size()
        zero_pad = E.new_zeros(bsz, n_head, max_len, 1)
        # bsz x n_head x -1 x (max_len+1)
        E = torch.cat([E, zero_pad], dim=-1).view(bsz, n_head, -1, max_len)
        indice = (torch.arange(max_len) * 2 + 1).to(E.device)
        E = E.index_select(index=indice, dim=-2).transpose(-1, -2)  # bsz x n_head x max_len x max_len

        return E


class MultiHeadAttn(nn.Module):
    def __init__(self, d_model, n_head, dropout=0.1, scale=False):
        """
        :param d_model:
        :param n_head:
        :param scale: 是否scale输出
        """
        super().__init__()
        assert d_model % n_head == 0

        self.n_head = n_head
        self.qkv_linear = nn.Linear(d_model, 3*d_model, bias=False)
        self.fc = nn.Linear(d_model, d_model)
        self.dropout_layer = nn.Dropout(dropout)

        if scale:
            self.scale = math.sqrt(d_model//n_head)
        else:
            self.scale = 1

    def forward(self, x, mask):
        """
        :param x: bsz x max_len x d_model
        :param mask: bsz x max_len
        :return:
        """
        batch_size, max_len, d_model = x.size()
        x = self.qkv_linear(x)
        q, k, v = torch.chunk(x, 3, dim=-1)
        q = q.view(batch_size, max_len, self.n_head, -1).transpose(1, 2)
        k = k.view(batch_size, max_len, self.n_head, -1).permute(0, 2, 3, 1)
        v = v.view(batch_size, max_len, self.n_head, -1).transpose(1, 2)

        attn = torch.matmul(q, k)  # batch_size x n_head x max_len x max_len
        attn = attn/self.scale
        attn.masked_fill_(mask=mask[:, None, None].eq(0), value=float('-inf'))

        attn = F.softmax(attn, dim=-1)  # batch_size x n_head x max_len x max_len
        attn = self.dropout_layer(attn)
        v = torch.matmul(attn, v)  # batch_size x n_head x max_len x d_model//n_head
        v = v.transpose(1, 2).reshape(batch_size, max_len, -1)
        v = self.fc(v)

        return v


class TransformerLayer(nn.Module):
    def __init__(self, d_model, self_attn, feedforward_dim, after_norm, dropout):
        """
        :param int d_model: 一般512之类的
        :param self_attn: self attention模块，输入为x:batch_size x max_len x d_model, mask:batch_size x max_len, 输出为
            batch_size x max_len x d_model
        :param int feedforward_dim: FFN中间层的dimension的大小
        :param bool after_norm: norm的位置不一样，如果为False，则embedding可以直接连到输出
        :param float dropout: 一共三个位置的dropout的大小
        """
        super().__init__()

        self.norm1 = nn.LayerNorm(d_model)
        self.norm2 = nn.LayerNorm(d_model)

        self.self_attn = self_attn

        self.after_norm = after_norm

        self.ffn = nn.Sequential(nn.Linear(d_model, feedforward_dim),
                                 nn.ReLU(),
                                 nn.Dropout(dropout),
                                 nn.Linear(feedforward_dim, d_model),
                                 nn.Dropout(dropout))

    def forward(self, x, mask):
        """
        :param x: batch_size x max_len x hidden_size
        :param mask: batch_size x max_len, 为0的地方为pad
        :return: batch_size x max_len x hidden_size
        """
        residual = x
        if not self.after_norm:
            x = self.norm1(x)

        x = self.self_attn(x, mask)
        x = x + residual
        if self.after_norm:
            x = self.norm1(x)
        residual = x
        if not self.after_norm:
            x = self.norm2(x)
        x = self.ffn(x)
        x = residual + x
        if self.after_norm:
            x = self.norm2(x)
        return x


class TransformerEncoder(nn.Module):
    def __init__(self, num_layers, d_model, n_head, feedforward_dim, dropout, after_norm=True, attn_type='naive',
                 scale=False, dropout_attn=None, pos_embed=None):
        super().__init__()
        if dropout_attn is None:
            dropout_attn = dropout
        self.d_model = d_model

        if pos_embed is None:
            self.pos_embed = None
        elif pos_embed == 'sin':
            self.pos_embed = SinusoidalPositionalEmbedding(d_model, 0, init_size=1024)
        elif pos_embed == 'fix':
            self.pos_embed = LearnedPositionalEmbedding(1024, d_model, 0)

        if attn_type == 'transformer':
            self_attn = MultiHeadAttn(d_model, n_head, dropout_attn, scale=scale)
        elif attn_type == 'adatrans':
            self_attn = RelativeMultiHeadAttn(d_model, n_head, dropout_attn, scale=scale)

        self.layers = nn.ModuleList([TransformerLayer(d_model, deepcopy(self_attn), feedforward_dim, after_norm, dropout)
                       for _ in range(num_layers)])

    def forward(self, x, mask):
        """
        :param x: batch_size x max_len
        :param mask: batch_size x max_len. 有value的地方为1
        :return:
        """
        if self.pos_embed is not None:
            x = x + self.pos_embed(mask)

        for layer in self.layers:
            x = layer(x, mask)

        return x


class TransformerCharEmbed(TokenEmbedding):
    def __init__(self, vocab: Vocabulary, embed_size: int = 30, char_emb_size: int = 30, word_dropout: float = 0,
                 dropout: float = 0, pool_method: str = 'max', activation='relu',
                 min_char_freq: int = 2, requires_grad=True, include_word_start_end=True,
                 char_attn_type='adatrans', char_n_head=3, char_dim_ffn=60, char_scale=False, char_pos_embed=None,
                 char_dropout=0.15, char_after_norm=False):
        """
        :param vocab: 词表
        :param embed_size: TransformerCharEmbed的输出维度。默认值为50.
        :param char_emb_size: character的embedding的维度。默认值为50. 同时也是Transformer的d_model大小
        :param float word_dropout: 以多大的概率将一个词替换为unk。这样既可以训练unk也是一定的regularize。
        :param dropout: 以多大概率drop character embedding的输出以及最终的word的输出。
        :param pool_method: 支持'max', 'avg'。
        :param activation: 激活函数，支持'relu', 'sigmoid', 'tanh', 或者自定义函数.
        :param min_char_freq: character的最小出现次数。默认值为2.
        :param requires_grad:
        :param include_word_start_end: 是否使用特殊的tag标记word的开始与结束
        :param char_attn_type: adatrans or naive.
        :param char_n_head: 多少个head
        :param char_dim_ffn: transformer中ffn中间层的大小
        :param char_scale: 是否使用scale
        :param char_pos_embed: None, 'fix', 'sin'. What kind of position embedding. When char_attn_type=relative, None is
            ok
        :param char_dropout: Dropout in Transformer encoder
        :param char_after_norm: the normalization place.
        """
        super(TransformerCharEmbed, self).__init__(vocab, word_dropout=word_dropout, dropout=dropout)

        assert char_emb_size%char_n_head == 0, "d_model should divide n_head."

        assert pool_method in ('max', 'avg')
        self.pool_method = pool_method
        # activation function
        if isinstance(activation, str):
            if activation.lower() == 'relu':
                self.activation = F.relu
            elif activation.lower() == 'sigmoid':
                self.activation = F.sigmoid
            elif activation.lower() == 'tanh':
                self.activation = F.tanh
        elif activation is None:
            self.activation = lambda x: x
        elif callable(activation):
            self.activation = activation
        else:
            raise Exception(
                "Undefined activation function: choose from: [relu, tanh, sigmoid, or a callable function]")

        logger.info("Start constructing character vocabulary.")
        # 建立char的词表
        self.char_vocab = _construct_char_vocab_from_vocab(vocab, min_freq=min_char_freq,
                                                           include_word_start_end=include_word_start_end)
        self.char_pad_index = self.char_vocab.padding_idx
        logger.info(f"In total, there are {len(self.char_vocab)} distinct characters.")
        # 对vocab进行index
        max_word_len = max(map(lambda x: len(x[0]), vocab))
        if include_word_start_end:
            max_word_len += 2
        self.register_buffer('words_to_chars_embedding', torch.full((len(vocab), max_word_len),
                                                                    fill_value=self.char_pad_index, dtype=torch.long))
        self.register_buffer('word_lengths', torch.zeros(len(vocab)).long())
        for word, index in vocab:
            # if index!=vocab.padding_idx:  # 如果是pad的话，直接就为pad_value了. 修改为不区分pad与否
            if include_word_start_end:
                word = ['<bow>'] + list(word) + ['<eow>']
            self.words_to_chars_embedding[index, :len(word)] = \
                torch.LongTensor([self.char_vocab.to_index(c) for c in word])
            self.word_lengths[index] = len(word)

        self.char_embedding = get_embeddings((len(self.char_vocab), char_emb_size))
        self.transformer = TransformerEncoder(1, char_emb_size, char_n_head, char_dim_ffn, dropout=char_dropout, after_norm=char_after_norm,
                                              attn_type=char_attn_type, pos_embed=char_pos_embed, scale=char_scale)
        self.fc = nn.Linear(char_emb_size, embed_size)

        self._embed_size = embed_size

        self.requires_grad = requires_grad

    def forward(self, words):
        """
        输入words的index后，生成对应的words的表示。
        :param words: [batch_size, max_len]
        :return: [batch_size, max_len, embed_size]
        """
        batch_size, original_max_len = words.size()
        words = self.drop_word(words)
        batch_size, max_len = words.size()
        chars = self.words_to_chars_embedding[words]  # batch_size x max_len x max_word_len
        word_lengths = self.word_lengths[words]  # batch_size x max_len
        max_word_len = word_lengths.max()
        chars = chars[:, :, :max_word_len]
        # 为mask的地方为1
        chars_masks = chars.eq(self.char_pad_index)  # batch_size x max_len x max_word_len 如果为0, 说明是padding的位置了
        char_embeds = self.char_embedding(chars)  # batch_size x max_len x max_word_len x embed_size
        char_embeds = self.dropout(char_embeds)
        reshaped_chars = char_embeds.reshape(batch_size * max_len, max_word_len, -1)

        trans_chars = self.transformer(reshaped_chars, chars_masks.eq(0).reshape(-1, max_word_len))
        trans_chars = trans_chars.reshape(batch_size, max_len, max_word_len, -1)
        trans_chars = self.activation(trans_chars)
        if self.pool_method == 'max':
            trans_chars = trans_chars.masked_fill(chars_masks.unsqueeze(-1), float('-inf'))
            chars, _ = torch.max(trans_chars, dim=-2)  # batch_size x max_len x H
        else:
            trans_chars = trans_chars.masked_fill(chars_masks.unsqueeze(-1), 0)
            chars = torch.sum(trans_chars, dim=-2) / chars_masks.eq(0).sum(dim=-1, keepdim=True).float()

        chars = self.fc(chars)

        return self.dropout(chars)


def make_positions(tensor, padding_idx):
    """Replace non-padding symbols with their position numbers.
    Position numbers begin at padding_idx+1. Padding symbols are ignored.
    """
    # The series of casts and type-conversions here are carefully
    # balanced to both work with ONNX export and XLA. In particular XLA
    # prefers ints, cumsum defaults to output longs, and ONNX doesn't know
    # how to handle the dtype kwarg in cumsum.
    mask = tensor.ne(padding_idx).int()
    return (
        torch.cumsum(mask, dim=1).type_as(mask) * mask
    ).long() + padding_idx


class SinusoidalPositionalEmbedding(nn.Module):
    """This module produces sinusoidal positional embeddings of any length.
    Padding symbols are ignored.
    """

    def __init__(self, embedding_dim, padding_idx, init_size=1568):
        super().__init__()
        self.embedding_dim = embedding_dim
        self.padding_idx = padding_idx
        self.weights = SinusoidalPositionalEmbedding.get_embedding(
            init_size,
            embedding_dim,
            padding_idx,
        )
        self.register_buffer('_float_tensor', torch.FloatTensor(1))

    @staticmethod
    def get_embedding(num_embeddings, embedding_dim, padding_idx=None):
        """Build sinusoidal embeddings.
        This matches the implementation in tensor2tensor, but differs slightly
        from the description in Section 3.5 of "Attention Is All You Need".
        """
        half_dim = embedding_dim // 2
        emb = math.log(10000) / (half_dim - 1)
        emb = torch.exp(torch.arange(half_dim, dtype=torch.float) * -emb)
        emb = torch.arange(num_embeddings, dtype=torch.float).unsqueeze(1) * emb.unsqueeze(0)
        emb = torch.cat([torch.sin(emb), torch.cos(emb)], dim=1).view(num_embeddings, -1)
        if embedding_dim % 2 == 1:
            # zero pad
            emb = torch.cat([emb, torch.zeros(num_embeddings, 1)], dim=1)
        if padding_idx is not None:
            emb[padding_idx, :] = 0
        return emb

    def forward(self, input):
        """Input is expected to be of size [bsz x seqlen]."""
        bsz, seq_len = input.size()
        max_pos = self.padding_idx + 1 + seq_len
        if max_pos > self.weights.size(0):
            # recompute/expand embeddings if needed
            self.weights = SinusoidalPositionalEmbedding.get_embedding(
                max_pos,
                self.embedding_dim,
                self.padding_idx,
            )
        self.weights = self.weights.to(self._float_tensor)

        positions = make_positions(input, self.padding_idx)
        return self.weights.index_select(0, positions.view(-1)).view(bsz, seq_len, -1).detach()

    def max_positions(self):
        """Maximum number of supported positions."""
        return int(1e5)  # an arbitrary large number


class LearnedPositionalEmbedding(nn.Embedding):
    """
    This module learns positional embeddings up to a fixed maximum size.
    Padding ids are ignored by either offsetting based on padding_idx
    or by setting padding_idx to None and ensuring that the appropriate
    position ids are passed to the forward function.
    """

    def __init__(
            self,
            num_embeddings: int,
            embedding_dim: int,
            padding_idx: int,
    ):
        super().__init__(num_embeddings, embedding_dim, padding_idx)

    def forward(self, input):
        # positions: batch_size x max_len, 把words的index输入就好了
        positions = make_positions(input, self.padding_idx)
        return super().forward(positions)


class TENER(nn.Module):
    def __init__(self, tag_vocab, embed, num_layers, d_model, n_head, feedforward_dim, dropout,
                 after_norm=True, attn_type='adatrans',  bi_embed=None,
                 fc_dropout=0.3, pos_embed=None, scale=False, dropout_attn=None):
        """
        :param tag_vocab: fastNLP Vocabulary
        :param embed: fastNLP TokenEmbedding
        :param num_layers: number of self-attention layers
        :param d_model: input size
        :param n_head: number of head
        :param feedforward_dim: the dimension of ffn
        :param dropout: dropout in self-attention
        :param after_norm: normalization place
        :param attn_type: adatrans, naive
        :param rel_pos_embed: position embedding的类型，支持sin, fix, None. relative时可为None
        :param bi_embed: Used in Chinese scenerio
        :param fc_dropout: dropout rate before the fc layer
        """
        super().__init__()

        self.embed = embed
        embed_size = self.embed.embed_size
        self.bi_embed = None
        if bi_embed is not None:
            self.bi_embed = bi_embed
            embed_size += self.bi_embed.embed_size

        self.in_fc = nn.Linear(embed_size, d_model)

        self.transformer = TransformerEncoder(num_layers, d_model, n_head, feedforward_dim, dropout,
                                              after_norm=after_norm, attn_type=attn_type,
                                              scale=scale, dropout_attn=dropout_attn,
                                              pos_embed=pos_embed)
        self.fc_dropout = nn.Dropout(fc_dropout)
        self.out_fc = nn.Linear(d_model, len(tag_vocab))

        trans = allowed_transitions(tag_vocab, include_start_end=True)
        self.crf = ConditionalRandomField(len(tag_vocab), include_start_end_trans=True, allowed_transitions=trans)

    def _forward(self, chars, target, bigrams=None):
        batch_size, original_seq_len = chars.size()
        if original_seq_len >= MAX_SEQ_LEN:
            original_chars = chars
            chars = chars[:, : MAX_SEQ_LEN]

        mask = chars.ne(0)
        chars = self.embed(chars)
        if self.bi_embed is not None:
            bigrams = self.bi_embed(bigrams)
            chars = torch.cat([chars, bigrams], dim=-1)

        chars = self.in_fc(chars)
        chars = self.transformer(chars, mask)
        chars = self.fc_dropout(chars)
        chars = self.out_fc(chars)

        if original_seq_len >= MAX_SEQ_LEN:
            new_chars = torch.zeros((batch_size, original_seq_len, chars.size(-1)), device=chars.device)
            new_chars[:, : MAX_SEQ_LEN] = chars
            chars = new_chars
            mask = original_chars.ne(0)

        logits = F.log_softmax(chars, dim=-1)
        if target is None:
            paths, _ = self.crf.viterbi_decode(logits, mask)
            return {'pred': paths}
        else:
            loss = self.crf(logits, target, mask)
            return {'loss': loss}

    def forward(self, chars, target, bigrams=None):
        return self._forward(chars, target, bigrams)

    def predict(self, chars, bigrams=None):
        return self._forward(chars, target=None, bigrams=bigrams)