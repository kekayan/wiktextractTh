# Wiktionary parser for extracting a lexicon and various other information
# from wiktionary.
#
# Copyright (c) 2018 Tatu Ylonen.  See file LICENSE and https://ylonen.org

import re
import bz2
import html
import collections
from lxml import etree
import wikitextparser
from wiktextract import wiktlangs
import wikitextparser as wtp
import json

# These XML tags are ignored when parsing.
ignore_tags = set(["sha1", "comment", "username", "timestamp",
                   "sitename", "dbname", "base", "generator", "case",
                   "ns", "restrictions", "contributor", "username",
                   "minor", "parentid", "namespaces", "revision",
                   "siteinfo", "mediawiki",
])

# Other tags are ignored inside these tags.
stack_ignore = ["contributor"]

# These Wiktionary templates are silently ignored (though some of them may be
# used when cleaning up titles and values).
ignored_templates = set([
    "-",
    "=",
    "*",
    "!",
    ",",
    "...",
    "AD",
    "BCE",
    "B.C.E.",
    "Book-B",
    "C.",
    "CE",
    "C.E.",
    "BC",
    "B.C.",
    "A.D.",
    "Clade",  # XXX Might want to dig information from this for hypernyms
    "CURRENTYEAR",
    "EtymOnLine",
    "EtymOnline",
    "IPAchar",
    "LR",
    "PAGENAME",
    "Q",
    "Webster 1913",
    "\\",
    "abbreviation-old",
    "af",
    "affix",
    "altcaps",
    "anchor",
    "ante",
    "attention",
    "attn",
    "bor",
    "borrowed",
    "bottom",
    "bottom2",
    "bottom3",
    "bottom4",
    "bullet",
    "checksense",
    "circa",
    "circa2",
    "cite",
    "cite book",
    "Cite news",
    "cite news",
    "cite-book",
    "cite-journal",
    "cite-magazine",
    "cite-news",
    "cite-newgroup",
    "cite-song",
    "cite-text",
    "cite-video",
    "cite-web",
    "cite web",
    "cog",
    "col-top",
    "col-bottom",
    "datedef",
    "def-date",
    "defdate",
    "defdt",
    "defn",
    "der",
    "der-bottom",
    "der-bottom2",
    "der-bottom3",
    "der-bottom4",
    "der-mid2",
    "der-mid3",
    "der-mid4",
    "der-mid",
    "derived",
    "dot",
    "doublet",
    "eggcorn of",
    "ellipsis",
    "em dash",
    "en dash",
    "etyl",
    "example needed",
    "examples",
    "examples-right",
    "frac",
    "g",  # gender - too rare to be useful
    "gloss-stub",
    "glossary",
    "hyp2",
    "hyp-top",
    "hyp-mid",
    "hyp-mid3",
    "hyp-bottom3",
    "hyp-bottom",
    "inh",
    "inherited",
    "interwiktionary",
    "ISO 639",
    "jump",
    "katharevousa",
    "ko-inline",
    "lang",
    "list",
    "ll",
    "lookfrom",
    "m",
    "mention",
    "mid2",
    "mid3",
    "mid4",
    "mid4",
    "middot",
    "multiple images",
    "nb...",
    "nbsp",
    "ndash",
    "no entry",
    "noncog",
    "noncognate",
    "nowrap",
    "nuclide",
    "overline",
    "phrasebook",
    "pedia",
    "pedialite",
    "picdic",
    "picdiclabel",
    "picdiclabel/new",
    "pos_v",
    "post",
    "quote-book",
    "quote-journal",
    "quote-magazine",
    "quote-news",
    "quote-newsgroup",
    "quote-song",
    "quote-text",
    "quote-video",
    "quote-web",
    "redirect",
    "rel-bottom",
    "rel-mid",
    "rel-mid2",
    "rel-mid3",
    "rel-mid4",
    "rfap",
    "rfc",
    "rfc-auto",
    "rfc-def",
    "rfc-header",
    "rfc-level",
    "rfc-subst",
    "rfc-tsort",
    "rfc-sense",
    "rfcite-sense",
    "rfd-redundant",
    "rfd-sense",
    "rfdate",
    "rfdatek",
    "rfdef",
    "rfe",
    "rfex",
    "rfexample",
    "rfm-sense",
    "rfgloss",
    "rfquote",
    "rfquote-sense",
    "rfquotek",
    "rft-sense",
    "rfv-sense",
    "rhymes",
    "rhymes",
    "see",
    "see also",
    "seeCites",
    "seemoreCites",
    "seemorecites",
    "seeMoreCites",
    "seeSynonyms",
    "sic",
    "smallcaps",
    "soplink",
    "spndash",
    "stroke order",
    "stub-gloss",
    "sub",
    "suffixsee",
    "sup",
    "syndiff",
    "t-check",
    "t+check",
    "table:colors/fi",
    "top2",
    "top3",
    "top4",
    "translation only",
    "trans-mid",
    "trans-bottom",
    "uncertain",
    "unk",
    "unsupported",
    "used in phrasal verbs",
    "was wotd",
    "wikisource1911Enc",
    "wikivoyage",
    "ws",
    "ws link",
    "zh-hg",
])

# This dictionary maps section titles in articles to parts-of-speech.  There
# is a lot of variety and misspellings, and this tries to deal with those.
pos_map = {
    "abbreviation": "abbrev",
    "acronym": "abbrev",
    "adjectival": "adj_noun",
    "adjectival noun": "adj_noun",
    "adjectival verb": "adj_verb",
    "adjective": "adj",
    "adjectuve": "adj",
    "adjectives": "adj",
    "adverb": "adv",
    "adverbs": "adv",
    "adverbial phrase": "adv_phrase",
    "affix": "affix",
    "adjective suffix": "affix",
    "article": "article",
    "character": "character",
    "circumfix": "circumfix",
    "circumposition": "circumpos",
    "classifier": "classifier",
    "clipping": "abbrev",
    "clitic": "clitic",
    "command form": "cmd",
    "command conjugation": "cmd_conj",
    "combining form": "combining_form",
    "comparative": "adj_comp",
    "conjunction": "conj",
    "conjuntion": "conj",
    "contraction": "abbrev",
    "converb": "converb",
    "counter": "counter",
    "determiner": "det",
    "diacritical mark": "character",
    "enclitic": "clitic",
    "enclitic particle": "clitic",
    "gerund": "gerund",
    "glyph": "character",
    "han character": "character",
    "han characters": "character",
    "ideophone": "noun",  # XXX
    "infix": "infix",
    "infinitive": "participle",
    "initialism": "abbrev",
    "interfix": "interfix",
    "interjection": "intj",
    "interrogative pronoun": "pron",
    "intransitive verb": "verb",
    "instransitive verb": "verb",
    "letter": "letter",
    "ligature": "character",
    "label": "character",
    "nom character": "character",
    "nominal nuclear clause": "clause",
    "νoun": "noun",
    "nouɲ": "noun",
    "noun": "noun",
    "nouns": "noun",
    "noum": "noun",
    "number": "num",
    "numeral": "num",
    "ordinal number": "ordinal",
    "participle": "participle",  # XXX
    "particle": "particle",
    "past participle": "participle",  # XXX
    "perfect expression": "participle",  # XXX
    "perfection expression": "participle",  # XXX
    "perfect participle": "participle",  # XXX
    "personal pronoun": "pron",
    "phrasal verb": "phrasal_verb",
    "phrase": "phrase",
    "phrases": "phrase",
    "possessive determiner": "det",
    "possessive pronoun": "det",
    "postposition": "postp",
    "predicative": "predicative",
    "prefix": "prefix",
    "preposition": "prep",
    "prepositions": "prep",
    "prepositional expressions": "prep",
    "prepositional phrase": "prep_phrase",
    "prepositional pronoun": "pron",
    "present participle": "participle",
    "preverb": "verb",
    "pronoun": "pron",
    "proper noun": "name",
    "proper oun": "name",
    "proposition": "prep",  # Appears to be a misspelling of preposition
    "proverb": "proverb",
    "punctuation mark": "punct",
    "punctuation": "punct",
    "relative": "conj",
    "root": "root",
    "syllable": "character",
    "suffix": "suffix",
    "suffix form": "suffix",
    "symbol": "symbol",
    "transitive verb": "verb",
    "verb": "verb",
    "verbal noun": "noun",
    "verbs": "verb",
    "digit": "digit",   # I don't think this is actually used in Wiktionary
}

# Set of all possible parts-of-speech returned by wiktionary reading.
PARTS_OF_SPEECH = set(pos_map.values())

# Templates ({{name|...}}) that will be replaced by the value of their
# first argument when cleaning up titles/values.
clean_arg1_tags = [
    "...",
    "Br. English form of",
    "W",
    "Wikipedia",
    "abb",
    "abbreviation of",
    "abbreviation",
    "acronym of",
    "agent noun of",
    "alt form of",
    "alt form",
    "alt form",
    "alt-form",
    "alt-sp",
    "altcaps",
    "alternate form of",
    "alternate spelling of",
    "alternative capitalisation of",
    "alternative capitalization of",
    "alternative case form of",
    "alternative form of",
    "alternative name of",
    "alternative name of",
    "alternative plural of",
    "alternative spelling of",
    "alternative term for",
    "alternative typography of",
    "altform",
    "altspell",
    "altspelling",
    "apocopic form of",
    "archaic form of",
    "archaic spelling of",
    "aspirate mutation of",
    "attributive form of",
    "attributive of",
    "caret notation of",
    "clip",
    "clipping of",
    "clipping",
    "common misspelling of",
    "comparative of",
    "contraction of",
    "dated form of",
    "dated spelling of",
    "deliberate misspelling of",
    "diminutive of",
    "ellipsis of",
    "ellipse of",
    "elongated form of",
    "en-archaic second-person singular of",
    "en-archaic third-person singular of",
    "en-comparative of",
    "en-irregular plural of",
    "en-past of",
    "en-second person singular past of",
    "en-second-person singular past of",
    "en-simple past of",
    "en-superlative of",
    "en-third person singular of",
    "en-third-person singular of",
    "euphemistic form of",
    "euphemistic spelling of",
    "eye dialect of",
    "eye dialect",
    "eye-dialect of",
    "femine of",
    "feminine noun of",
    "feminine plural of",
    "feminine singular of",
    "form of",
    "former name of",
    "gerund of",
    "hard mutation of",
    "honoraltcaps",
    "imperative of",
    "informal form of"
    "informal spelling of",
    "ja-l",
    "ja-r",
    "lenition of",
    "masculine plural of",
    "masculine singular of",
    "misconstruction of",
    "misspelling of",
    "mixed mutation of",
    "n-g",
    "native or resident of",
    "nb...",
    "neuter plural of",
    "neuter singular of",
    "ngd",
    "nobr",
    "nominative plural of",
    "non-gloss definition",
    "non-gloss",
    "nonstandard form of",
    "nonstandard spelling of",
    "nowrap",
    "obsolete form of",
    "obsolete spelling of",
    "obsolete typography of",
    "overwrite",
    "past of",
    "past sense of",
    "past tense of",
    "pedlink",
    "pedlink",
    "plural form of",
    "plural of",
    "present of",
    "present particle of",
    "present tense of",
    "pronunciation spelling of",
    "pronunciation spelling",
    "pronunciation respelling of",
    "rare form of",
    "rare spelling of",
    "rareform",
    "second person singular past of",
    "second-person singular of",
    "second-person singular past of",
    "short for",
    "short form of",
    "short of",
    "singular form of",
    "singular of",
    "slim-wikipedia",
    "soft mutation of",
    "standard form of",
    "standard spelling of",
    "standspell",
    "sub",
    "sup",
    "superlative of",
    "superseded spelling of",
    "swp",
    "taxlink",
    "taxlinknew",
    "uncommon spelling of",
    "unsupported",
    "verb",
    "vern",
    "w",
    "wikipedia",
    "wikisaurus",
    "wikispecies",
    "zh-m",
]

# Templates that will be replaced by their second argument when cleaning up
# titles/values.
clean_arg2_tags = [
    "zh-l",
    "ja-l",
    "l",
    "defn",
    "w",
    "m",
    "mention",
]

# Templates that will be replaced by their third argument when cleaning up
# titles/values.
clean_arg3_tags = [
    "w2",
]

# Templates that will be replaced by a value when cleaning up titles/values.
# The replacements may refer to the first argument of the template using \1.
#
# Note that there is a non-zero runtime cost for each replacement in this
# dictionary; keep its size reasonable.
clean_replace_map = {
    "en dash": " - ",
    "em dash": " - ",
    "ndash": " - ",
    "\\": " / ",
    "...": "...",
    "BCE": "BCE",
    "B.C.E.": "B.C.E.",
    "CE": "CE",
    "C.E.": "C.E.",
    "BC": "BC",
    "B.C.": "B.C.",
    "A.D.": "A.D.",
    "AD": "AD",
    "Latn-def": "latin character",
    "sumti": r"x\1",
    "inflection of": r"inflection of \1",
    "initialism of": r"initialism of \1",
    "synonym of": r"synonym of \1",
    "given name": r"\1 given name",
    "forename": r"\1 given name",
    "historical given name": r"\1 given name",
    "surname": r"surname",
    "taxon": r"taxonomic \1",
    "SI-unit": "unit of measurement",
    "SI-unit-abb2": "unit of measurement",
    "SI-unit-2": "unit of measurement",
    "SI-unit-np": "unit of measurement",
    "gloss": r"(\1)",
}

# Note: arg_re contains two sets of parenthesis
arg_re = (r"(\|[-_a-zA-Z0-9]+=[^}|]+)*"
          r"\|(([^|{}]|\{\{[^}]*\}\}|\[\[[^]]+\]\]|\[[^]]+\])*)")

# Matches more arguments and end of template
args_end_re = r"(" + arg_re + r")*\}\}"

# Regular expression for replacing templates by their arg1.  arg1 is \3
clean_arg1_re = re.compile(r"(?s)\{\{(" +
                           "|".join(re.escape(x) for x in clean_arg1_tags) +
                           r")" +
                           arg_re + args_end_re)

# Regular expression for replacing templates by their arg2.  arg2 is \4
clean_arg2_re = re.compile(r"(?s)\{\{(" +
                           "|".join(re.escape(x) for x in clean_arg2_tags) +
                           r")" + arg_re + arg_re + args_end_re)

# Regular expression for replacing templates by their arg3.  arg3 is \6
clean_arg3_re = re.compile(r"(?s)\{\{(" +
                           "|".join(re.escape(x) for x in clean_arg3_tags) +
                           r")" + arg_re + arg_re + arg_re + args_end_re)

# Mapping from German verb form arguments to "canonical" values in
# word sense tags."""
de_verb_form_map = {
    # Keys under which to look for values
    "_keys": [2, 3, 4, 5, 6, 7, 8, 9],
    # Mapping of values in arguments to canonical values
    "1": ["1"],
    "2": ["2"],
    "3": ["3"],
    "pr": ["present participle"],
    "pp": ["past participle"],
    "i": ["imperative"],
    "s": ["singular"],
    "p": ["plural"],
    "g": ["present"],
    "v": ["past"],
    "k1": ["subjunctive 1"],
    "k2": ["subjunctive 2"],
}

# Mapping from Spanish verb form values to "canonical" values."""
es_verb_form_map = {
    # Argument names under which we search for values.
    "_keys": ["mood", "tense", "num", "number", "pers", "person", "formal",
              "sense", "sera", "gen", "gender"],
    # Mapping of values in arguments to canonical values
    "ind": ["indicative"],
    "indicative": ["indicative"],
    "subj": ["subjunctive"],
    "subjunctive": ["subjunctive"],
    "imp": ["imperative"],
    "imperative": ["imperative"],
    "cond": ["conditional"],
    "par": ["past participle"],
    "part": ["past participle"],
    "participle": ["past participle"],
    "past-participle": ["past participle"],
    "past participle": ["past participle"],
    "adv": ["present participle"],
    "adverbial": ["present participle"],
    "ger": ["present participle"],
    "gerund": ["present participle"],
    "gerundive": ["present participle"],
    "gerundio": ["present participle"],
    "present-participle": ["present participle"],
    "present participle": ["present participle"],
    "pres": ["present"],
    "present": ["present"],
    "pret": ["preterite"],
    "preterit": ["preterite"],
    "preterite": ["preterite"],
    "imp": ["past"],
    "imperfect": ["past"],
    "fut": ["future"],
    "future": ["future"],
    "cond": ["conditional"],
    "conditional": ["conditional"],
    "s": ["singular"],
    "sing": ["singular"],
    "singular": ["singular"],
    "p": ["plural"],
    "pl": ["plural"],
    "plural": ["plural"],
    "1": ["1"],
    "first": ["1"],
    "first-person": ["1"],
    "2": ["2"],
    "second": ["2"],
    "second person": ["2"],
    "second-person": ["2"],
    "3": ["3"],
    "third": ["3"],
    "third person": ["3"],
    "third-person": ["3"],
    "y": ["formal"],
    "yes": ["formal"],
    "no": ["not formal"],
    "+": ["affirmative"],
    "aff": ["affirmative"],
    "affirmative": ["affirmative"],
    "-": ["negative"],
    "neg": ["negative"],
    "negative": ["negative"],
    "se": ["se"],
    "ra": ["ra"],
    "m": ["masculine"],
    "masc": ["masculine"],
    "masculine": ["masculine"],
    "f": ["feminine"],
    "fem": ["feminine"],
    "feminine": ["feminine"],
}


# Mapping from a template name (without language prefix) for the main word
# (e.g., fi-noun, fi-adj, en-verb) to permitted parts-of-speech in which
# it could validly occur.  This is used as just a sanity check to give
# warnings about probably incorrect coding in Wiktionary.
template_allowed_pos_map = {
    "abbr": ["abbrev"],
    "abbr": ["abbrev"],
    "noun": ["noun", "abbrev", "pron", "name", "num"],
    "plural noun": ["noun", "name"],
    "proper noun": ["noun", "name", "proper-noun"],
    "proper-noun": ["name", "noun", "proper-noun"],
    "verb": ["verb", "phrase"],
    "plural noun": ["noun"],
    "adv": ["adv"],
    "particle": ["adv", "particle"],
    "adj": ["adj"],
    "pron": ["pron", "noun"],
    "name": ["name", "noun", "proper-noun"],
    "adv": ["adv", "intj", "conj", "particle"],
    "phrase": ["phrase"],
}


def parse_text(word, text, ctx):
    """Parses the text of a Wiktionary page and returns a list of dictionaries,
    one for each word/part-of-speech defined on the page for the languages
    specified by ``capture_languages``.  ``word`` is page title, and ``text``
    is page text in Wikimedia format.  Other arguments indicate what is
    captured."""
    assert isinstance(word, str)
    assert isinstance(text, str)
    assert isinstance(ctx, WiktionaryTarget)
    if "Thesaurus:" not in word:
        return
    # print(word)

    wordss=[s.strip() for s in text.splitlines() if s]
    # print(wordss)
    key = None
    data = {}
    data["word"] = wordss[0]
    syno=[]
    anto=[]
    hypo=[]
    hyper=[]
    inst=[]
    mero=[]
    holy=[]
    for aword in wordss:
        # aword=re.sub(r'[^\w]', ' ', aword).strip()
        if "{{ws beginlist}}" == aword or "{{ws endlist}}" == aword:
            continue
        if "Synonyms" == re.sub(r'[^\w]', ' ', aword).strip():
            key="a"
        elif "Antonyms" == re.sub(r'[^\w]', ' ', aword).strip():
            key="b"
        elif "Hyponyms" == re.sub(r'[^\w]', ' ', aword).strip():
            key="c"
        elif "Hypernyms" == re.sub(r'[^\w]', ' ', aword).strip():
            key="d"
        elif "Instances" == re.sub(r'[^\w]', ' ', aword).strip():
            key="e"
        elif "Meronyms" == re.sub(r'[^\w]', ' ', aword).strip():
            key="f"
        elif "Holonyms" == re.sub(r'[^\w]', ' ', aword).strip():
            key="g"
        elif "=====Various====="==aword or "===See also==="==aword or "===Further reading==="==aword:
            key="Dont care now"
        if key=="a" and "Synonyms" != re.sub(r'[^\w]', ' ', aword).strip():
            parsed = wtp.parse(aword)
            try:
                syno.append(parsed.templates[0].arguments[0].value)
            except:
                continue

        if key=="b" and "Antonyms" != re.sub(r'[^\w]', ' ', aword).strip():
            parsed = wtp.parse(aword)
            try:
                anto.append(parsed.templates[0].arguments[0].value)
            except:
                continue
        if key=="c" and "Hyponyms"!= re.sub(r'[^\w]', ' ', aword).strip():
            parsed = wtp.parse(aword)
            try:
                hypo.append(parsed.templates[0].arguments[0].value)
            except:
                continue
        if key=="d" and "Hypernyms" != re.sub(r'[^\w]', ' ', aword).strip():
            parsed = wtp.parse(aword)
            try:
                hyper.append(parsed.templates[0].arguments[0].value)
            except:
                continue
        if key=="e" and "Instances" != re.sub(r'[^\w]', ' ', aword).strip():
            try:
                parsed = wtp.parse(aword)
                inst.append(parsed.templates[0].arguments[0].value)
            except:
                continue
        if key=="f" and "Meronyms" != re.sub(r'[^\w]', ' ', aword).strip():
            parsed = wtp.parse(aword)
            try:
                mero.append(parsed.templates[0].arguments[0].value)
            except:
                continue
        if key=="g" and "Holonyms" != re.sub(r'[^\w]', ' ', aword).strip():
            parsed = wtp.parse(aword)
            try:
                holy.append(parsed.templates[0].arguments[0].value)
            except:
                continue

    data["Synonyms"]=syno
    data["Antonyms"] = anto
    data["Hyponyms"] = hypo
    data["Hypernyms"] = hyper
    data["Instances"] = inst
    data["Meronyms"] = mero
    data["Holonyms"] = holy

    with open("Output.txt", "a+") as text_file:
        text_file.write(json.dumps(data))
        text_file.write('\n')






class WiktionaryTarget(object):
    """This class is used for XML parsing the Wiktionary dump file."""

    def __init__(self, word_cb, capture_cb,
                 capture_languages, capture_translations,
                 capture_pronunciation, capture_linkages,
                 capture_compounds, capture_redirects):
        assert callable(word_cb)
        assert capture_cb is None or callable(capture_cb)
        assert isinstance(capture_languages, (list, tuple, set))
        for x in capture_languages:
            assert isinstance(x, str)
        assert capture_translations in (True, False)
        assert capture_linkages in (True, False)
        assert capture_translations in (True, False)
        self.word_cb = word_cb
        self.capture_cb = capture_cb
        self.capture_languages = capture_languages
        self.capture_translations = capture_translations
        self.capture_pronunciation = capture_pronunciation
        self.capture_linkages = capture_linkages
        self.capture_compounds = capture_compounds
        self.capture_redirects = capture_redirects
        self.tag = None
        self.namespaces = {}
        self.stack = []
        self.text = None
        self.title = None
        self.pageid = None
        self.redirect = None
        self.model = None
        self.format = None
        self.language_counts = collections.defaultdict(int)
        self.pos_counts = collections.defaultdict(int)
        self.section_counts = collections.defaultdict(int)


    def start(self, tag, attrs):
        """This is called whenever an XML start tag is encountered."""
        idx = tag.find("}")
        if idx >= 0:
            tag = tag[idx + 1:]
        attrs = {re.sub(r".*}", "", k): v for k, v in attrs.items()}
        tag = tag.lower()
        #while tag in self.stack:
        #    self.end(self.stack[-1])
        self.tag = tag
        self.stack.append(tag)
        self.attrs = attrs
        self.data = []
        if tag == "page":
            self.text = None
            self.title = None
            self.pageid = None
            self.redirect = None
            self.model = None
            self.format = None

    def end(self, tag):
        """This function is called whenever an XML end tag is encountered."""
        idx = tag.find("}")
        if idx >= 0:
            tag = tag[idx + 1:]
        tag = tag.lower()
        ptag = self.stack.pop()
        assert tag == ptag
        attrs = self.attrs
        data = "".join(self.data).strip()
        self.data = []
        if tag in ignore_tags:
            return
        for t in stack_ignore:
            if t in self.stack:
                return
        if tag == "id":
            if "revision" in self.stack:
                return
            self.pageid = data
        elif tag == "title":
            self.title = data
        elif tag == "text":
            self.text = data
        elif tag == "redirect":
            self.redirect = attrs.get("title")
        elif tag == "namespace":
            key = attrs.get("key")
            self.namespaces[key] = data
        elif tag == "model":
            self.model = data
            if data not in ("wikitext", "Scribunto", "css", "javascript",
                            "sanitized-css"):
                print("UNRECOGNIZED MODEL", data)
        elif tag == "format":
            self.format = data
            if data not in ("text/x-wiki", "text/plain",
                            "text/css", "text/javascript"):
                print("UNRECOGNIZED FORMAT", data)
        elif tag == "page":
            pageid = self.pageid
            title = self.title
            redirect = self.redirect
            if self.model in ("css", "sanitized-css", "javascript",
                              "Scribunto"):
                return
            if redirect:
                if self.capture_redirects:
                    data = {"redirect": redirect, "word": title}
                    self.word_cb(data)
            else:
                parse_text(title, self.text, self)

        else:
            print("UNSUPPORTED", tag, len(data), attrs)

    def data(self, data):
        """This function is called for data within an XML tag."""
        self.data.append(data)

    def close(self):
        """This function is called when parsing is complete."""
        return None


def parse_wiktionary(path, word_cb, capture_cb=None,
                     languages=["English", "Translingual"],
                     translations=False,
                     pronunciations=False,
                     linkages=False,
                     compounds=False,
                     redirects=False):
    """Parses Wiktionary from the dump file ``path`` (which should point
    to a "enwiktionary-<date>-pages-articles.xml.bz2" file.  This
    calls ``capture_cb(title)`` for each raw page (if provided), and
    if it returns True, and calls ``word_cb(data)`` for all words
    defined for languages in ``languages``.  The other keyword
    arguments control what data is to be extracted."""
    assert isinstance(path, str)
    assert callable(word_cb)
    assert capture_cb is None or callable(capture_cb)
    assert isinstance(languages, (list, tuple, set))
    for x in languages:
        assert isinstance(x, str)
        assert x in wiktlangs.languages
    assert translations in (True, False)
    assert pronunciations in (True, False)
    assert linkages in (True, False)
    assert compounds in (True, False)
    assert redirects in (True, False)

    # Open the input file.
    if path.endswith(".bz2"):
        wikt_f = bz2.BZ2File(path, "r", buffering=(4 * 1024 * 1024))
    else:
        wikt_f = open(path, "rb", buffering=(4 * 1024 * 1024))

    try:
        # Create parsing context.
        ctx = WiktionaryTarget(word_cb, capture_cb,
                               languages, translations,
                               pronunciations, linkages, compounds,
                               redirects)
        # Parse the XML file.
        parser = etree.XMLParser(target=ctx)
        etree.parse(wikt_f, parser)
    finally:
        wikt_f.close()

    return ctx