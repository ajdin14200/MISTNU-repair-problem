from centralized_algorithm.main_wc_cycles import *
from centralized_algorithm.main_wc_smt import *
from structures import *

def display_solution(res, p_res, original_bounds, fairness):

    print("Repaired bounds:")
    for n, lst in res.items():
        for i, (l, u) in enumerate(lst):
            print(
                f"  {n}: original bounds -> {original_bounds[n][i]} new bounds -> [{l}, {u}] (~= [{float(l):.2f}, {float(u):.2f}])")
    print("")

    if fairness:
        print("Percentages:")
        for n, v in p_res.items():
            print(f"  p of {n}: {v} (~= {float(v):.2f})")

if __name__ == "__main__":

    parser = argparse.ArgumentParser(description='Encoder for controllability of temporal problems')


    parser.add_argument('inputFile', metavar='inputFile', type=str, help='The problem to encode')
    parser.add_argument('--fairness', '-f', action="store_true")
    parser.add_argument('--solver', metavar='solver', type=str, help='Which solver to use')

    args = parser.parse_args()


    mas = MAS()
    mas.fromFile(args.inputFile)

    if args.solver:

        if args.solver == "wc_cycles":


            agent_cycles, map_contracts = compute_controllability(mas)  # Get all the negative cycles of all agents

            res_bool, res, p_res, original_bounds = repair_cycle(mas, agent_cycles, map_contracts, "z3", use_secondary=args.fairness)

            display_solution(res, p_res, original_bounds, args.fairness)



        if args.solver == "wc_smt":

            res_bool, res, p_res, original_bounds = max_bounds(mas, "z3", controllability="weak", use_secondary=args.fairness)
            display_solution(res, p_res, original_bounds, args.fairness)



