# coding=utf-8
from __future__ import unicode_literals

import json
import traceback as tb
import unittest

from mock import patch

from snips_nlu.constants import CUSTOM_ENGINE
from snips_nlu.intent_classifier import feature_extraction
from snips_nlu.intent_classifier.feature_extraction import (
    Featurizer, default_tfidf_vectorizer, get_utterances_entities)
from snips_nlu.languages import Language
from snips_nlu.tokenization import tokenize_light


class TestFeatureExtraction(unittest.TestCase):
    @patch("snips_nlu.intent_classifier.feature_extraction."
           "CLUSTER_USED_PER_LANGUAGES", {Language.EN: "brown_clusters"})
    def test_should_be_serializable(self):
        # Given
        language = Language.EN
        tfidf_vectorizer = default_tfidf_vectorizer(language)

        pvalue_threshold = 0.42
        featurizer = Featurizer(language, tfidf_vectorizer=tfidf_vectorizer,
                                pvalue_threshold=pvalue_threshold)
        dataset = {
            "entities": {
                "entity2": {
                    "data": [
                        {
                            "value": "entity1",
                            "synonyms": ["entity1"]
                        }
                    ],
                    "use_synonyms": True
                }
            }
        }
        queries = [
            "hello world",
            "beautiful world",
            "hello here",
            "bird birdy",
            "beautiful bird"
        ]
        classes = [0, 0, 0, 1, 1]

        featurizer.fit(dataset, queries, classes)

        # When
        serialized_featurizer = featurizer.to_dict()

        # Then
        try:
            dumped = json.dumps(serialized_featurizer).decode("utf8")
        except:
            self.fail("Featurizer dict should be json serializable to utf8.\n"
                      "Traceback:\n%s" % tb.format_exc())

        try:
            _ = Featurizer.from_dict(json.loads(dumped))
        except:
            self.fail("SnipsNLUEngine should be deserializable from dict with "
                      "unicode values\nTraceback:\n%s" % tb.format_exc())

        vocabulary = tfidf_vectorizer.vocabulary_
        idf_diag = tfidf_vectorizer._tfidf._idf_diag.data.tolist()

        best_features = featurizer.best_features
        entity_utterances_to_entity_names = {"entity1": ["entity2"]}

        expected_serialized = {
            "language_code": "en",
            "tfidf_vectorizer": {"idf_diag": idf_diag, "vocab": vocabulary},
            "best_features": best_features,
            "pvalue_threshold": pvalue_threshold,
            "entity_utterances_to_entity_names":
                entity_utterances_to_entity_names
        }
        self.assertDictEqual(expected_serialized, serialized_featurizer)

    @patch("snips_nlu.intent_classifier.feature_extraction."
           "CLUSTER_USED_PER_LANGUAGES", {Language.EN: "brown_clusters"})
    def test_should_be_deserializable(self):
        # Given
        language = Language.EN
        idf_diag = [1.52, 1.21, 1.04]
        vocabulary = {"hello": 0, "beautiful": 1, "world": 2}

        best_features = [0, 1]
        pvalue_threshold = 0.4
        entity_utterances_to_entity_names = {"entity_1": ["entity_1"]}

        featurizer_dict = {
            "language_code": language.iso_code,
            "tfidf_vectorizer": {"idf_diag": idf_diag, "vocab": vocabulary},
            "best_features": best_features,
            "pvalue_threshold": pvalue_threshold,
            "entity_utterances_to_entity_names":
                entity_utterances_to_entity_names
        }

        # When
        featurizer = Featurizer.from_dict(featurizer_dict)

        # Then
        self.assertEqual(featurizer.language, language)
        self.assertListEqual(
            featurizer.tfidf_vectorizer._tfidf._idf_diag.data.tolist(),
            idf_diag)
        self.assertDictEqual(featurizer.tfidf_vectorizer.vocabulary_,
                             vocabulary)
        self.assertListEqual(featurizer.best_features, best_features)
        self.assertEqual(featurizer.pvalue_threshold, pvalue_threshold)

        self.assertDictEqual(
            featurizer.entity_utterances_to_entity_names,
            {
                k: set(v) for k, v
                in entity_utterances_to_entity_names.iteritems()
            })

    def test_get_utterances_entities(self):
        # Given
        dataset = {
            "intents": {
                "intent1": {
                    "utterances": [],
                    "engineType": CUSTOM_ENGINE
                }
            },
            "entities": {
                "entity1": {
                    "data": [
                        {
                            "value": "entity 1",
                            "synonyms": ["alternative entity 1"]
                        },
                        {
                            "value": "éntity 1",
                            "synonyms": ["alternative entity 1"]
                        }
                    ],
                    "use_synonyms": False,
                    "automatically_extensible": False
                },
                "entity2": {
                    "data": [
                        {
                            "value": "entity 1",
                            "synonyms": []
                        },
                        {
                            "value": "Éntity 2",
                            "synonyms": ["Éntity_2", "Alternative entity 2"]
                        }
                    ],
                    "use_synonyms": True,
                    "automatically_extensible": False
                }
            },
            "language": "en",
            "snips_nlu_version": "0.0.1"
        }

        # When
        utterance_to_entity_names = get_utterances_entities(dataset)

        # Then
        expected_utterance_to_entity_names = {
            "entity 1": {"entity1", "entity2"},
            "éntity 1": {"entity1"},
            "Éntity_2": {"entity2"},
            "Éntity 2": {"entity2"},
            "Alternative entity 2": {"entity2"}
        }
        self.assertDictEqual(
            utterance_to_entity_names, expected_utterance_to_entity_names)

    @patch("snips_nlu.intent_classifier.feature_extraction.get_word_clusters")
    @patch("snips_nlu.intent_classifier.feature_extraction.stem")
    def test_preprocess_queries(self, mocked_stem, mocked_word_cluster):
        # Given
        language = Language.EN

        def _stem(t):
            if t == "beautiful":
                s = "beauty"
            elif t == "birdy":
                s = "bird"
            elif t == "entity":
                s = "ent"
            else:
                s = t
            return s

        def stem_function(text, language):
            return language.default_sep.join(
                [_stem(t) for t in tokenize_light(text, language)])

        feature_extraction.CLUSTER_USED_PER_LANGUAGES = {
            Language.EN: "brown_clusters"
        }

        mocked_word_cluster.return_value = {
            "brown_clusters": {
                "beautiful": "cluster_1",
                "birdy": "cluster_2",
                "entity": "cluster_3"
            }
        }

        mocked_stem.side_effect = stem_function

        dataset = {
            "intents": {
                "intent1": {
                    "utterances": [],
                    "engineType": CUSTOM_ENGINE
                }
            },
            "entities": {
                "entity_1": {
                    "data": [
                        {
                            "value": "entity 1",
                            "synonyms": ["alternative entity 1"]
                        },
                        {
                            "value": "éntity 1",
                            "synonyms": ["alternative entity 1"]
                        }
                    ],
                    "use_synonyms": False,
                    "automatically_extensible": False
                },
                "entity_2": {
                    "data": [
                        {
                            "value": "entity 1",
                            "synonyms": []
                        },
                        {
                            "value": "Éntity 2",
                            "synonyms": ["Éntity_2", "Alternative entity 2"]
                        }
                    ],
                    "use_synonyms": True,
                    "automatically_extensible": False
                }
            },
            "language": "en",
            "snips_nlu_version": "0.0.1"
        }

        queries = [
            "hÉllo wOrld Éntity_2",
            "beauTiful World entity 1",
            "Bird bïrdy",
            "beauTiful éntity 1 bIrd Éntity_2"
        ]
        labels = [0, 0, 1, 1]

        featurizer = Featurizer(language).fit(
            dataset, queries, labels)

        # When
        queries = featurizer.preprocess_queries(queries)

        # Then
        expected_queries = [
            "hello world entity_2 entityfeatureentity_2",
            "beauty world ent 1 entityfeatureentity_1 entityfeatureentity_2 "
            "cluster_1 cluster_3",
            "bird bird",
            "beauty ent 1 bird entity_2 entityfeatureentity_1 "
            "entityfeatureentity_2 entityfeatureentity_2 cluster_1"
        ]

        self.assertListEqual(queries, expected_queries)
