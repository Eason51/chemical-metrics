import paper_count_per_year

targetName = "kras"
[a, b] = paper_count_per_year.get_paper_count_per_year(targetName.lower())
print(a)
print()
print(b)