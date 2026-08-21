import re
import unicodedata

import nltk
import spacy
from nltk.stem.snowball import SnowballStemmer
from nltk.util import ngrams
from nltk import TweetTokenizer
from spacy.lang.en import English
from spacy.lang.es import Spanish
from spacy.tokens import Token

_STEMMERS = {"es": SnowballStemmer("spanish"), "en": SnowballStemmer("english")}

if not Token.has_extension("stem"):
    Token.set_extension(
        "stem",
        getter=lambda token: _STEMMERS.get(token.lang_, _STEMMERS["en"]).stem(token.text),
    )


class TextProcessing(object):
    name = "Text Processing"
    lang = "es"

    def __init__(self, lang: str = "es"):
        self.lang = lang
        self.nlp = TextProcessing.load_spacy(lang=lang)

    @staticmethod
    def load_spacy(lang: str):
        result = None
        try:
            if lang == "es":
                result = spacy.load("es_core_news_sm")
            else:
                result = spacy.load("en_core_web_sm")
        except Exception as e:
            print("Error load_spacy: {0}".format(e))
        return result

    def analysis_pipe(self, text: str):
        doc = None
        try:
            if self.nlp is not None:
                doc = self.nlp(text=text)
        except Exception as e:
            print("Error analysis_pipe: {0}".format(e))
        return doc

    @staticmethod
    def proper_encoding(text: str):
        result = ""
        try:
            text = unicodedata.normalize("NFD", text)
            text = text.encode("ascii", "ignore")
            result = text.decode("utf-8")
        except Exception as e:
            print("Error proper_encoding: {0}".format(e))
        return result

    @staticmethod
    def stopwords(text: str, lang: str = "es"):
        result = ""
        try:
            nlp = Spanish() if lang == "es" else English()
            doc = nlp(text)
            token_list = [token.text for token in doc]
            sentence = []
            for word in token_list:
                lexeme = nlp.vocab[word]
                if not lexeme.is_stop:
                    sentence.append(word)
            result = " ".join(sentence)
        except Exception as e:
            print("Error stopwords: {0}".format(e))
        return result

    @staticmethod
    def remove_patterns(text: str):
        result = ""
        try:
            text = re.sub(r"\©|\×|\⇔|\_|\»|\«|\~|\#|\$|\€|\Â|\�|\¬", "", text)
            text = re.sub(r"\,|\;|\:|\!|\¡|\’|\‘|\”|\“|\"|\'|\`", "", text)
            text = re.sub(r"\}|\{|\[|\]|\(|\)|\<|\>|\?|\¿|\°|\|", "", text)
            text = re.sub(r"\/|\-|\+|\*|\=|\^|\%|\&|\$", "", text)
            text = re.sub(r"\b\d+(?:\.\d+)?\s+", "", text)
            result = text.lower()
        except Exception as e:
            print("Error remove_patterns: {0}".format(e))
        return result

    @staticmethod
    def transformer(text: str, stopwords: bool = False, lang: str = "es"):
        result = ""
        try:
            text_out = text.lower()
            text_out = re.sub("[\U0001f000-\U000e007f]", " ", text_out)
            text_out = re.sub(
                r"(?i)\b((?:https?://|www\d{0,3}[.]|[a-z0-9.\-]+[.][a-z]{2,4}/)(?:[^\s()<>]+|\(([^\s()<>]+"
                r"|(\([^\s()<>]+\)))*\))+(?:\(([^\s()<>]+|(\([^\s()<>]+\)))*\)|[^\s`!()\[\]{};:\'\".,<>?«»“”‘’]))",
                " ",
                text_out,
            )
            text_out = re.sub("@([A-Za-z0-9_]{1,40})", " ", text_out)
            text_out = re.sub("#([A-Za-z0-9_]{1,40})", " ", text_out)
            text_out = TextProcessing.remove_patterns(text_out)
            text_out = TextProcessing.stopwords(text_out, lang) if stopwords else text_out
            text_out = re.sub(r"\s+", " ", text_out).strip()
            result = text_out if text_out != "" else None
        except Exception as e:
            print("Error transformer: {0}".format(e))
        return result

    @staticmethod
    def tokenizer(text: str):
        val = []
        try:
            text_tokenizer = TweetTokenizer()
            val = text_tokenizer.tokenize(text)
        except Exception as e:
            print("Error tokenizer: {0}".format(e))
        return val

    @staticmethod
    def make_ngrams(text: str, num: int):
        result = []
        try:
            tokens = TextProcessing.tokenizer(text)
            n_grams = ngrams(tokens, num)
            result = [" ".join(grams) for grams in n_grams]
        except Exception as e:
            print("Error make_ngrams: {0}".format(e))
        return result

    def tagger(self, text: str):
        result = None
        try:
            list_tagger = []
            doc = self.analysis_pipe(text=text)
            if doc is not None:
                for token in doc:
                    item = {
                        "text": token.text,
                        "lemma": token.lemma_,
                        "stem": token._.stem,
                        "pos": token.pos_,
                        "tag": token.tag_,
                        "dep": token.dep_,
                        "is_alpha": token.is_alpha,
                        "is_stop": token.is_stop,
                    }
                    list_tagger.append(item)
            result = list_tagger
        except Exception as e:
            print("Error tagger: {0}".format(e))
        return result

    def noun_phrases(self, text: str):
        result = []
        try:
            doc = self.analysis_pipe(text=text)
            if doc is not None:
                result = [chunk.text.strip() for chunk in doc.noun_chunks if len(chunk.text.strip()) > 2]
        except Exception as e:
            print("Error noun_phrases: {0}".format(e))
        return result
