import argparse

from centralized_algorithm.main_wc_cycles import *
from centralized_algorithm.main_smt import *
from distributed_algorithm.synchronous_backtracking_algorithm import *
from structures import *

# This function display the bounds of the contract after running a repair algorithm.
# It shows the original bounds and the new bounds of each contract
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


# Here we ask the parameter to the user and run the appropriate repair algorithm
# You are free to modify this part to run all the benchmark according to your settings for evaluate the algorithms
# for example the criteria we used is: the time to repair, the time to find all negative cycles, the number and size of negative cycles
# Please note that for the SMT repair algorithm we used the Z3 solver but you are free to use another one accessible from PySMT librairy
if __name__ == "__main__":

    parser = argparse.ArgumentParser(description='Encoder for controllability of temporal problems')


    parser.add_argument('inputFile', metavar='inputFile', type=str, help='The problem to encode')
    parser.add_argument('--solver', metavar='solver', type=str, help='Which solver to use')
    parser.add_argument('--fairness', '-f', action="store_true")
    #can only be used with the linear_cycle option.
    # This is an additional optimization function that provides some fairness among the contracts reduction, i.e., maximize the number of contracts that can be reduced by the same amount


    args = parser.parse_args()


    mistnu = MISTNU() # This is equivalent to the MISTNU model
    mistnu.fromFile(args.inputFile) # here we read the instance to test

    SMT_solver = "z3"  # here we use the Z3 solver

    if args.solver:

        if args.solver == "linear_cycles":  # here we call the linear repair algorithm that finds and repair all negative cycles in a centralized way


            agent_cycles, map_contracts = compute_controllability(mistnu)  # Get all the negative cycles of all agents

            res_bool, res, p_res, original_bounds = repair_cycle(mistnu, agent_cycles, map_contracts, SMT_solver, use_secondary=args.fairness)

            display_solution(res, p_res, original_bounds, args.fairness)

        if args.solver == "SMT":

            res_bool, res, p_res, original_bounds = onbounds(mistnu, SMT_solver, use_secondary=args.fairness)

            display_solution(res, p_res, original_bounds, args.fairness)



        if args.solver == "SBT":  # here we call the linear repair algorithm that finds and repair all negative cycles in a centralized way

            agent_cycles, map_contracts = compute_controllability(mistnu)  # Get all the negative cycles of all agents

            run(mistnu, agent_cycles, map_contracts)




    else :
        print("Please enter a method using the --solver argument")


