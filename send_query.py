import argparse
import os
import time

import matplotlib.pyplot as plt
import numpy as np
import psycopg2

from joins.tools import save_predictions_to_file


def send_query(dataset, method_name, query_file, save_folder, iteration=None):
    conn = psycopg2.connect(
        options="-c statement_timeout=100s",
        database=dataset,
        user="quincy",
        password="postgres",
        host="127.0.0.1",
        port=5433,
    )
    cursor = conn.cursor()

    with open(query_file, "r") as f:
        queries = f.readlines()  # [587:588]

    # cursor.execute('SET debug_card_est=true')
    # cursor.execute('SET print_sub_queries=true')
    # cursor.execute('SET print_single_tbl_queries=true')

    # cursor.execute("SET ml_joinest_enabled=true;")
    # cursor.execute("SET join_est_no=0;")
    # cursor.execute(f"SET ml_joinest_fname='{method_name}';")

    save_file_name = method_name.split(".txt")[0] + ".log"
    print("saved  to " + save_file_name)
    planning_time = []
    execution_time = []
    predictions = []
    ratios = []
    truths = []
    for no, query_str in enumerate(queries):
        if "||" in query_str:
            query = query_str.split("||")[0]
        print(f"Executing query {no}")
        # start = time.time()
        # cursor.execute("EXPLAIN ANALYZE " + query)
        # res = cursor.fetchall()
        # # print(res[0])
        # print("-" * 80)
        # for line in res:
        #     print(line)
        # print("-" * 80)
        # planning_time.append(float(res[-2][0].split(":")[-1].split("ms")[0].strip()))
        # execution_time.append(float(res[-1][0].split(":")[-1].split("ms")[0].strip()))
        # end = time.time()
        # print(
        #     f"{no}-th query finished in {end-start}, with planning_time {planning_time[no]} ms and execution_time {execution_time[no]} ms"
        # )
        # est = [line[0] for line in res if "width=0" in line[0]]
        # assert len(est) == 1
        # pred = float(est[0].split("rows=")[1].split(" ")[0])
        # truth = float(est[0].split("rows=")[2].split(" ")[0])
        # print("est is ", pred)
        # print("truth is ", truth)
        try:
            start = time.time()
            cursor.execute(query)
            res = cursor.fetchall()
            end = time.time()
            # print(res)
            # assert res[0][0] == truth
            # ratios.append(pred / truth)
            # predictions.append(pred)
            truths.append(res[0][0])
            execution_time.append(end - start)
            print(f"{no}-th query finished in {end-start}ms")
            # cursor.execute("rollback()")
            # conn.rollback()
            # conn.commit()
        except psycopg2.errors.QueryCanceled:
            truths.append(-1)
            execution_time.append(-1)
            print(f"{no}-th query timeout!")
            conn.rollback()

        # for row in res:
        #     predictions.append(row[0])
        #     with open(save_file_name, "a+") as f:
        #         #
        #         f.write(query_str[:-1] + "||" + str(row[0]) + "\n")
    # print(predictions)
    # logbins = np.logspace(np.log10(min(ratios)), np.log10(max(ratios)), 100)
    # plt.xscale("log")
    # plt.hist(ratios, bins=logbins)
    # plt.show()

    cursor.close()
    conn.close()

    # save_predictions_to_file(
    #     predictions,
    #     planning_time,
    #     "postgres",
    #     "postgres-time",
    #     "results/stats/single_table/postgres.csv",
    # )

    save_predictions_to_file(
        truths,
        execution_time,
        "truth",
        "truth-time-postgres",
        "results/stats/multiple_tables/truth_2014.csv",
    )

    # if iteration:
    #     np.save(
    #         save_folder + f"plan_time_{save_file_name}_iter{iteration}",
    #         np.asarray(planning_time),
    #     )
    #     np.save(
    #         save_folder + f"exec_time_{save_file_name}_iter{iteration}",
    #         np.asarray(execution_time),
    #     )
    # else:
    #     np.save(save_folder + f"plan_time_{save_file_name}", np.asarray(planning_time))
    #     np.save(save_folder + f"exec_time_{save_file_name}", np.asarray(execution_time))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dataset", default="stats2014", help="Which dataset to be used"
    )
    parser.add_argument(
        "--method_name",
        default="workloads/stats_CEB/estimates/truth.txt",
        help="save estimates",
    )
    parser.add_argument(
        "--query_file",
        default="workloads/stats_CEB/sub_plan_queries/stats_CEB_sub_queries.sql",
        help="Query file location",
    )
    parser.add_argument(
        "--with_true_card",
        action="store_true",
        help="Is true cardinality included in the query?",
    )
    parser.add_argument(
        "--save_folder",
        default="workloads/stats_CEB/estimates/",
        help="Query file location",
    )
    parser.add_argument(
        "--iteration", type=int, default=None, help="Number of iteration to read"
    )

    args = parser.parse_args()

    if args.iteration:
        for i in range(args.iteration):
            send_query(
                args.dataset, args.method_name, args.query_file, args.save_folder, i + 1
            )
    else:
        send_query(args.dataset, args.method_name, args.query_file, args.save_folder)
