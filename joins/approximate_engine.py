import time
from enum import Enum

import numpy as np
import scipy.integrate as integrate

from joins.base_logger import logger
from joins.join_graph import get_join_hyper_graph
from joins.parser import parse_query_simple
from joins.schema_base import identify_conditions, identify_key_values
from joins.stats.schema import get_stats_relevant_attributes
from joins.table import Column, TableContainer


class QueryType(Enum):
    TwoTableNoSelection = 1
    TwoTableRightSelection = 2
    MultiTableSingleJoinKeyNoSelection = 3
    MultiTableMultiJoinKeyNoSelection = 4
    SelectionOnJoinKey = 5
    NotSupported = 20


class ApproximateEngine:
    def __init__(self,  models: dict[str, TableContainer] = None, auto_grid=True) -> None:
        self.models: dict = models
        self.auto_grid = auto_grid
        self.all_keys, self.equivalent_keys, self.table_keys = identify_key_values(
            models['schema'])
        self.join_keys, self.relevant_keys, self.counters = get_stats_relevant_attributes(
            models['schema'])

    def query(self, query_str):

        # print("keys: \n", self.models.keys())

        logger.info("QUERY [%s]", query_str)
        query_type, tables_all, join_cond, non_key_conditions, tbl_and_join_key_dict, join_key_in_each_table = parse_query_type(
            query_str, self.equivalent_keys)

        if query_type == QueryType.SelectionOnJoinKey:
            logger.warning(
                "selection on join key is not supported yet, but coule be easily supported.")
            return
        if query_type == QueryType.TwoTableNoSelection:
            return simple_card(self.models, tables_all, join_cond,
                               self.relevant_keys, self.counters)
        if query_type == QueryType.TwoTableRightSelection:
            return right_table_selection_card(self.models, tables_all, join_cond, non_key_conditions,
                                              self.relevant_keys, self.counters)
        if query_type == QueryType.MultiTableSingleJoinKeyNoSelection:
            return multiple_table_same_join_column(self.models, tables_all, join_cond, non_key_conditions, tbl_and_join_key_dict, join_key_in_each_table, self.relevant_keys, self.counters)
        else:
            logger.info("QueryType: %s", query_type)
            logger.warning("not implemented yet")
            return

    def integrate1d(self, model_name, l, h):
        if self.auto_grid:
            return integrate.quad(lambda x: self.models[model_name].predict(x), l, h)
        else:
            logger.warning("grid integral is not implemented yet")

    def integrate2d(self,):
        pass


def simple_card(models: dict[str, TableContainer], tables_all, join_cond, relevant_keys, counters, grid=1000):
    # t11 = time.time()
    assert (len(join_cond) == 1)
    col_models = []
    n_models = []
    conditions = [cond.split(" = ") for cond in join_cond][0]
    # print("conditions", conditions)
    # print("join_cond:", join_cond)
    # print("tables_all: ", tables_all)
    t1, k1 = conditions[0].split(".")
    t2, k2 = conditions[1].split(".")
    # print(t1, k1)
    n1, n2 = counters[t1], counters[t2]

    mdl1, mdl2 = models[t1].pdfs[k1], models[t2].pdfs[k2]
    # print(mdl1)
    mins = max(mdl1.min, mdl2.min)
    maxs = min(mdl1.max, mdl2.max)
    assert (mins < maxs)

    # t2 = time.time()
    # # *
    # result = integrate.quad(lambda x: mdl1.pdf.predict(
    #     x)*mdl2.pdf.predict(x), mins, maxs, limit=500)[0] * n1*n2
    # print("result: ", result)
    # t3 = time.time()

    x = np.linspace(mins, maxs, grid)
    width = x[1] - x[0]
    # print("width:", width)
    pred1 = mdl1.pdf.predict(x)
    pred2 = mdl2.pdf.predict(x)
    result = width*np.sum(np.multiply(pred1, pred2))*n1*n2  # *width*n1*n2
    # result = integrate.quad(lambda x: mdl1.pdf.predict(
    #     x)*mdl2.pdf.predict(x), mins, maxs)[0]*n1*n2
    # logger.info("result: %f", result)
    # logger.info("time cost for this query is %f", (t3-t2))
    # logger.info("time cost for this query is %f", (time.time()-t3))
    # logger.info("time cost for this query is %f", (time.time()-t11))
    return result


def right_table_selection_card(models: dict[str, TableContainer], tables_all, join_cond, non_key_conditions, relevant_keys, counters, grid=100):
    # t11 = time.time()
    assert (len(join_cond) == 1)

    tbl_and_join_key_dict, join_key_in_each_table = get_tbl_and_join_key_dict(
        join_cond)
    # logger.info("tbl_and_join_key_dict %s", tbl_and_join_key_dict)

    assert (len(non_key_conditions) == 1)

    right_table_name = list(non_key_conditions.keys())[0]
    left_table_name = list(tbl_and_join_key_dict.keys())
    left_table_name.remove(right_table_name)
    left_table_name = left_table_name[0]

    # get the non_key
    non_keys = non_key_conditions[right_table_name]

    bounds = get_bounds(non_keys)

    assert (len(bounds) == 1)  # only one selection condition at this moment.
    extra_col = list(bounds.keys())[0]

    mdl1 = models[left_table_name].pdfs[tbl_and_join_key_dict[left_table_name][0]]
    mdl2 = models[right_table_name].correlations[tbl_and_join_key_dict[right_table_name][0]][extra_col]
    mins = max(mdl1.min, mdl2.min[0])
    maxs = min(mdl1.max, mdl2.max[0])
    assert (mins < maxs)
    n1, n2 = counters[left_table_name], counters[right_table_name]

    bound = bounds[extra_col]
    if mdl2.min[1] > bound[0]:
        bound[0] = mdl2.min[1]
    if mdl2.max[1] < bound[1]:
        bound[1] = mdl2.max[1]

    grid_x_size = 300
    grid_y_size = 200
    # t2 = time.time()
    x_grid = np.linspace(mins, maxs, grid_x_size)
    width_x = x_grid[1] - x_grid[0]
    y_grid = np.linspace(bound[0], bound[1], grid_y_size)
    width_y = y_grid[1] - y_grid[0]

    # t3 = time.time()
    pred1 = mdl1.pdf.predict(x_grid)
    # t4 = time.time()

    pred2 = mdl2.pdf.predict_grid(x_grid, y_grid)
    # t5 = time.time()

    pred1 = np.array([pred1 for _ in range(grid_y_size)]
                     ).reshape(grid_x_size, grid_y_size)

    result = np.sum(np.multiply(pred1, pred2))*width_x*width_y*n1*n2
    # t6 = time.time()
    # logger.info("time cost for grid %f", (t3-t2))
    # logger.info("time cost for 1d predict %f", (t4-t3))
    # logger.info("time cost for 2d predict is %f", (t5-t4))
    # logger.info("time cost for integral is %f", (t6-t5))

    # logger.info("result: %f", result)
    # logger.info("time cost for this query is %f", (time.time()-t11))
    return result


def multiple_table_same_join_column(models: dict[str, TableContainer], tables_all, join_cond, non_key_conditions, tbl_and_join_key_dict, join_key_in_each_table, relevant_keys, counters, grid=100):
    # logger.info(query_type, tables_all, join_cond, non_key_conditions)
    # logger.info("tables_all %s", tables_all)
    # logger.info("join_cond %s", join_cond)
    # logger.info("non_key_conditions %s", non_key_conditions)
    # logger.info("tbl_and_join_key_dict %s", tbl_and_join_key_dict)
    # logger.info("join_key_in_each_table %s", join_key_in_each_table)

    same_col_join_model_container = []
    cnt = 1
    for t in tbl_and_join_key_dict:
        col = tbl_and_join_key_dict[t][0]
        same_col_join_model_container.append(models[t].pdfs[col])
        cnt *= models[t].size
    # logger.info("models %s", same_col_join_model_container)
    # logger.info("cnt %s", cnt)
    result = cnt * \
        intergrate_1d_multi_table_same_join_key(same_col_join_model_container)
    return result


def parse_query_type(query_str, equivalent_keys):
    tables_all, table_queries, join_cond, join_keys = parse_query_simple(
        query_str)
    equivalent_group = get_join_hyper_graph(
        join_keys, equivalent_keys)
    key_conditions, non_key_conditions = identify_conditions(
        table_queries, join_keys)
    tbl_and_join_key_dict, join_key_in_each_table = get_tbl_and_join_key_dict(
        join_cond)

    if key_conditions:
        return QueryType.SelectionOnJoinKey, tables_all, join_cond, non_key_conditions, tbl_and_join_key_dict, join_key_in_each_table

    # currently, no selection on the join key
    # assert (len(key_conditions) == 0)

    if not non_key_conditions:  # simple case, no selections
        # a table has at most 1 join key
        if max([len(val)for val in tbl_and_join_key_dict.values()]) == 1:
            if len(tables_all) == 2:
                return QueryType.TwoTableNoSelection, tables_all, join_cond, non_key_conditions, tbl_and_join_key_dict, join_key_in_each_table
            else:
                return QueryType.MultiTableSingleJoinKeyNoSelection, tables_all, join_cond, non_key_conditions, tbl_and_join_key_dict, join_key_in_each_table
        else:  # exist table with two or more join keys
            logger.warning("not implemented yet")
            return
    else:
        return QueryType.TwoTableRightSelection, tables_all, join_cond, non_key_conditions, tbl_and_join_key_dict, join_key_in_each_table


def get_tbl_and_join_key_dict(join_cond):
    join_cond = [i.replace(' ', '') for i in join_cond]
    join_table_and_keys = [c.split("=")
                           for c in join_cond]  # [i.split(".") for i in
    tbl_and_join_key_dict = {}
    # logger.info("join_table_and_keys %s", join_table_and_keys)

    # if len(join_table_and_keys) == 1:  # simple 2 table join
    #     for i in join_table_and_keys[0]:
    #         t_name, k_name = i.split(".")
    #         tbl_and_join_key_dict[t_name] = k_name
    #     return tbl_and_join_key_dict

    for condi in join_table_and_keys:
        for kv in condi:
            t_name, k_name = kv.split(".")
            if t_name not in tbl_and_join_key_dict:
                tbl_and_join_key_dict[t_name] = set([k_name])
            else:
                tbl_and_join_key_dict[t_name].add(k_name)
    for t_name in tbl_and_join_key_dict:
        tbl_and_join_key_dict[t_name] = list(tbl_and_join_key_dict[t_name])

    # logger.info("tbl_and_join_key_dict %s", tbl_and_join_key_dict)
    # exit()

    join_key_in_each_table = {}
    for [i1, i2] in join_table_and_keys:
        # print("join_table_and_keys", join_table_and_keys)
        # for [i1, i2] in cond:
        if i1 not in join_key_in_each_table:
            join_key_in_each_table[i1] = [i2]
        else:
            join_key_in_each_table[i1].append(i2)

        if i2 not in join_key_in_each_table:
            join_key_in_each_table[i2] = [i1]
        else:
            join_key_in_each_table[i2].append(i1)
    # logger.info("join_key_in_each_table %s", join_key_in_each_table)

    # max_occurence = max([len(val)for val in join_key_in_each_table.values()])
    # max_keys = [k for k in join_key_in_each_table if len(
    #     join_key_in_each_table[k]) == max_occurence]

    # print("max_keys", max_keys)
    # print("max_occurence", max_occurence)

    return tbl_and_join_key_dict, join_key_in_each_table
    # exit()


def get_bounds(non_keys):
    bounds = {}
    for non_k in non_keys:
        k = non_k.split(".")[1]
        domain = [-np.Infinity, np.Infinity]
        for op in non_keys[non_k]:
            if '>' in op:
                domain[0] = non_keys[non_k][op]
            elif '<' in op:
                domain[1] = non_keys[non_k][op]
            elif '=' in op:
                domain[0], domain[1] = non_keys[non_k][op] - \
                    0.5, non_keys[non_k][op]+0.5
        bounds[k] = domain
    return bounds


def intergrate_1d_multi_table_same_join_key(models: list[Column], grid_size=10000):
    mins = [m.min for m in models if isinstance(m, Column)]
    maxs = [m.max for m in models if isinstance(m, Column)]
    mins = max(mins)-0.5
    maxs = min(maxs)+0.5

    xs, width = np.linspace(mins, maxs, grid_size, retstep=True)
    predictions = []
    for m in models:
        predictions.append(m.pdf.predict(xs)*width)
    pred0 = predictions[0]
    if len(predictions) > 1:
        for p in predictions[1:]:
            pred0 = np.multiply(pred0, p)

    result = np.sum(pred0)
    return result
