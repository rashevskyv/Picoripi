import re

class GlossaryManagerMock:
    @staticmethod
    def _get_word_stem_pattern(word: str) -> str:
        if len(word) <= 2:
            return re.escape(word)
        endings = ['а', 'е', 'и', 'і', 'о', 'у', 'я', 'ь', 'ий', 'ій', 'ая', 'яя', 'ое', 'ее']
        stem = word
        for e in sorted(endings, key=len, reverse=True):
            if word.lower().endswith(e):
                stem = word[:-len(e)]
                break
        if len(stem) < 2:
             stem = word[:3] if len(word) > 3 else word
        return rf"{re.escape(stem)}[а-яА-ЯіїІїЄєґҐ']*"

    @classmethod
    def build_translation_regex(cls, term: str) -> re.Pattern:
        variations = [v.strip() for v in term.split(';') if v.strip()]
        patterns = []
        sep = r"(?:\s+|[\u2028\u2029\u200B\u200C\u200D]|<[^>]+>|\{[^}]+\}|\[[^\]]+\])+"
        for var in variations:
            words = var.split()
            if len(words) > 1:
                parts = [cls._get_word_stem_pattern(word) for word in words]
                patterns.append(rf"(?<!\w){sep.join(parts)}(?!\w)")
            else:
                patterns.append(rf"(?<!\w){cls._get_word_stem_pattern(var)}(?!\w)")
        combined_pattern = f"(?:{'|'.join(patterns)})"
        return re.compile(combined_pattern, re.IGNORECASE)

text = "пронизує {color:red}годину сутінків{color:white}..."
term = "година сутінків"

regex = GlossaryManagerMock.build_translation_regex(term)
print("Regex pattern:", repr(regex.pattern))
for match in regex.finditer(text):
    start, end = match.span()
    print(f"Match range: {start} to {end}")
    print(f"Match substring: {repr(text[start:end])}")
    print(f"Character after match: {repr(text[end:end+1])}")
