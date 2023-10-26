import os
import pickle
import unittest

import numpy as np

from joins.approximate_engine import ApproximateEngine
from joins.args import parse_args
from joins.stats.train_stats import train_stats
from joins.tools import q_error


class TestApproximateEngineMethod(unittest.TestCase):

    def __init__(self, methodName: str = "runTest") -> None:
        super().__init__(methodName)
        self.model_name = "model_stats_gaussian_100"
    # train needed models

    # @classmethod
    # def setUpClass(cls):
    #     # ['biweight', 'box', 'cosine', 'epa', 'exponential', 'gaussian', 'tri', 'tricube', 'triweight']
    #     arguments = ["--train", "--grid", "100", "--kernel", "gaussian"]
    #     args = parse_args(arguments)
    #     train_stats(args)

    # # remove trained models for test purposes
    # @classmethod
    # def tearDownClass(cls):
    #     for file in os.listdir("models"):
    #         print("files: " + file)
    #         if "100" in file:
    #             os.remove("models/"+file)

    def test_simple_query(self):
        query = "SELECT COUNT(*) FROM votes as v, posts as p WHERE p.Id = v.PostId"
        with open("models/"+self.model_name+".pkl", 'rb') as f:
            model = pickle.load(f)
        engine = ApproximateEngine(model)
        res = engine.query(query)
        truth = 328064
        self.assertTrue(q_error(res, truth) < 2)

    def test_one_selection_query(self):
        query = "SELECT COUNT(*) FROM users as u, badges as b WHERE b.UserId= u.Id AND u.UpVotes>=0"
        with open("models/"+self.model_name+".pkl", 'rb') as f:
            model = pickle.load(f)
        engine = ApproximateEngine(model)
        res = engine.query(query)
        truth = 79851
        self.assertTrue(q_error(res, truth) < 3)

    # def test_multiple_table_same_join_column(self):
    #     query = "SELECT COUNT(*) FROM badges as b, comments as c, users as u WHERE c.UserId = u.Id AND b.UserId = u.Id"
    #     with open("models/"+self.model_name+".pkl", 'rb') as f:
    #         model = pickle.load(f)
    #     engine = ApproximateEngine(model)
    #     res = engine.query(query)
    #     truth = 79851
    #     self.assertTrue(q_error(res, truth) < 3)


if __name__ == '__main__':
    unittest.main()
