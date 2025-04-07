import copy
from src.structures import *



def topological_ordering(child_per_tp, vz):
    #print("vz: ",vz.name)
    rank  = {}
    for tp in child_per_tp.keys():
        rank[tp] = 0
    next = [vz]
    while len(next) > 0:
        tp = next[0]
        next.pop(0)
        for constraint in child_per_tp[tp]:
            dest = constraint.atoms[0].dest
            rank_dest = rank[tp] + 1

            if rank[dest]< rank_dest:
                rank[dest] = rank_dest
                next.append(dest)
    #print("rank: ",rank)
    return rank




def get_divergent(problem):
    child_per_tp = {}  # get graph + give the childs per tp which identifies divergent time-points
    parent_per_tp = {} # give the parent of each tp which dentifies convergent time-point
    graph = {}

    divergents_tps = set()
    convergents_tps = set()

    for name, tp in problem.timePoints.items():
        child_per_tp[tp] = []
        parent_per_tp[tp] = []
        graph[tp] = []
    for constraint in problem.constraints:
        source = constraint.atoms[0].source
        dest = constraint.atoms[0].dest
        l = constraint.atoms[0].lowerBound
        u = constraint.atoms[0].upperBound
        child_per_tp[source].append(constraint)
        parent_per_tp[dest].append(constraint)

        graph[source].append(constraint)
        atoms = set()
        atoms.add(AtomicConstraint(dest,source,-u,-l))
        inverse_constraint = Constraint(atoms,constraint.contingent,constraint.process)
        graph[dest].append(inverse_constraint)

    for k,v in child_per_tp.items():
        if len(v) > 1:
            divergents_tps.add(k)

    for k,v in parent_per_tp.items():
        if len(v) > 1:
            convergents_tps.add(k)


    return graph, child_per_tp, divergents_tps, convergents_tps


def is_path_Inner_cycle(dest, path, rank, divergents_tps):
    pathsTP = path[2]
    bool1 = dest in pathsTP
    bool2 = dest in divergents_tps
    #print("dest ", dest)
    #print("origine tp : ", pathsTP[0])
    #print("rank ",rank, " + size rank ",len(rank))
    bool3 = rank[dest] < rank[pathsTP[0]]
    return bool1 or (bool2 and bool3)


def max_new_path(path, constraint, dest):

    l = constraint.atoms[0].lowerBound
    u = constraint.atoms[0].upperBound
    new_path = []
    path_contingents = [ i for i in path[1]]
    path_requirements = [i for i in path[3]]

    if constraint.contingent:
        new_path.append(path[0] + l)
        path_contingents.append(constraint)

    else:
        new_path.append(path[0] + u)
        path_requirements.append(constraint)

    new_path_tps = [i for i in path[2]]
    new_path_tps.append(dest)

    new_path.append(path_contingents)
    new_path.append(new_path_tps)
    new_path.append(path_requirements)

    return new_path


def min_new_path(path, constraint, dest):
    l = constraint.atoms[0].lowerBound
    u = constraint.atoms[0].upperBound
    new_path = []
    path_contingents = [i for i in path[1]]
    path_requirements = [i for i in path[3]]

    if constraint.contingent:
        new_path.append(path[0] + u)
        path_contingents.append(constraint)

    else:
        new_path.append(path[0] + l)
        path_requirements.append(constraint)

    new_path_tps = [i for i in path[2]]
    new_path_tps.append(dest)

    new_path.append(path_contingents)
    new_path.append(new_path_tps)
    new_path.append(path_requirements)

    return new_path

def contains_all_contingent(p1, p2):
    for c in p1:
        if c not in p2:
            return False
    return  True
def add_max_path(new_path, max_paths, path_to_redo):


    if len(new_path[1]) ==0 and max_paths[0] != None: # requirement but a requirement already exist

        if new_path[0] < max_paths[0][0]:
            if max_paths[0] in path_to_redo:
                path_to_redo.remove(max_paths[0])
            path_to_redo.append(new_path)
            max_paths.pop(0)
            max_paths.insert(0,new_path)


            index_to_remove = 0
            for i in range(1, len(max_paths)):

                if max_paths[i-index_to_remove][0] > new_path[0]:
                    if max_paths[i-index_to_remove] in path_to_redo:
                       path_to_redo.remove(max_paths[i-index_to_remove])
                    max_paths.pop(i-index_to_remove)
                    index_to_remove+=1

    elif len(new_path[1]) ==0 and max_paths[0] == None:  # first requirement

        index_to_remove = 0
        for i in range(1, len(max_paths)):
            if max_paths[i-index_to_remove][0] > new_path[0]:
                if max_paths[i-index_to_remove] in path_to_redo:
                    path_to_redo.remove(max_paths[i-index_to_remove])
                max_paths.pop(i - index_to_remove)
                index_to_remove += 1

        max_paths.pop(0)
        max_paths.insert(0, new_path)
        path_to_redo.append(new_path)

    elif len(new_path[1]) > 0 and  max_paths[0] != None:  # contingent with a requirement


        if new_path[0] < max_paths[0][0]:  # if the contingent is strictier than the requirement

            index_to_remove = 0
            can_add = True
            for i in range(1, len(max_paths)):

                if len(new_path[1]) == len(max_paths[i-index_to_remove][1]) and contains_all_contingent(new_path[1], max_paths[i-index_to_remove][1]):

                    if new_path[0] < max_paths[i-index_to_remove][0]:
                        if max_paths[i-index_to_remove] in path_to_redo:
                            path_to_redo.remove(max_paths[i-index_to_remove])
                        max_paths.pop(i - index_to_remove)
                        index_to_remove += 1
                    else: can_add = False
                    break
            if can_add:
                path_to_redo.append(new_path)
                max_paths.append(new_path)


    else: # contingent with only contingent

        index_to_remove = 0
        can_add = True
        for i in range(1, len(max_paths)):

            if len(new_path[1]) == len(max_paths[i][1]) and contains_all_contingent(new_path[1], max_paths[i-index_to_remove][1]):

                if new_path[0] < max_paths[i-index_to_remove][0]:
                    if max_paths[i - index_to_remove] in path_to_redo:
                        path_to_redo.remove(max_paths[i - index_to_remove])
                    max_paths.pop(i - index_to_remove)
                    index_to_remove += 1
                else: can_add = False
                break
        if can_add:
            path_to_redo.append(new_path)
            max_paths.append(new_path)


def add_min_path(new_path, min_paths, path_to_redo):
    if len(new_path[1]) == 0 and min_paths[0] != None:  # requirement but a requirement already exist

        if new_path[0] > min_paths[0][0]:
            if min_paths[0] in path_to_redo:
                path_to_redo.remove(min_paths[0])
            path_to_redo.append(new_path)
            min_paths.pop(0)
            min_paths.insert(0, new_path)

            index_to_remove = 0
            for i in range(1, len(min_paths)):

                if min_paths[i-index_to_remove][0] < new_path[0]:
                    if min_paths[i-index_to_remove] in path_to_redo:
                        path_to_redo.remove(min_paths[i-index_to_remove])
                    min_paths.pop(i - index_to_remove)
                    index_to_remove += 1

    elif len(new_path[1]) == 0 and min_paths[0] == None:  # first requirement

        index_to_remove = 0
        for i in range(1, len(min_paths)):
            if min_paths[i-index_to_remove][0] < new_path[0]:
                if min_paths[i-index_to_remove] in path_to_redo:
                   path_to_redo.remove(min_paths[i-index_to_remove])
                min_paths.pop(i - index_to_remove)
                index_to_remove += 1

        min_paths.pop(0)
        min_paths.insert(0, new_path)
        path_to_redo.append(new_path)


    elif len(new_path[1]) > 0 and min_paths[0] != None:  # contingent with a requirement

        if new_path[0] > min_paths[0][0]:  # if the contingent is strictier than the requirement

            index_to_remove = 0
            can_add = True
            for i in range(1, len(min_paths)):

                if len(new_path[1]) == len(min_paths[i-index_to_remove][1]) and contains_all_contingent(new_path[1], min_paths[i-index_to_remove][1]):

                    if new_path[0] > min_paths[i-index_to_remove][0]:
                        if min_paths[i - index_to_remove] in path_to_redo:
                            path_to_redo.remove(min_paths[i - index_to_remove])
                        min_paths.pop(i - index_to_remove)
                        index_to_remove += 1
                    else: can_add = False
                    break
            if can_add:
                path_to_redo.append(new_path)
                min_paths.append(new_path)

    else:  # contingent with only contingent

        index_to_remove = 0
        can_add = True
        for i in range(1, len(min_paths)):

            if len(new_path[1]) == len(min_paths[i-index_to_remove][1]) and contains_all_contingent(new_path[1], min_paths[i-index_to_remove][1]):

                if new_path[0] > min_paths[i-index_to_remove][0]:
                    if min_paths[i - index_to_remove] in path_to_redo:
                        path_to_redo.remove(min_paths[i - index_to_remove])
                    min_paths.pop(i - index_to_remove)
                    index_to_remove += 1
                else: can_add = False
                break
        if can_add:
            path_to_redo.append(new_path)
            min_paths.append(new_path)


def check_weak_cycle(min_p, max_p, cycles):

    if min_p[0] > max_p[0]:
        cycles.append([min_p, max_p])
def check_cycles_controllaiblity(max_path, min_path, cycles):

    for tp in max_path.keys():
        if tp in min_path:
            index_max = 1 if max_path[tp][0] == None else 0
            index_min = 1 if min_path[tp][0] == None else 0

            for i in range(index_max, len(max_path[tp])):
                for j in range(index_min, len(min_path[tp])):
                    can_check= True
                    max_p = max_path[tp][i]
                    min_p = min_path[tp][j]

                    if len(min_p[2]) == 2 and len(max_p[2])>2:
                        if len(min_p[1]) >0 and min_p[1][0] in max_p[1]:
                            can_check = False

                    elif len(max_p[2]) == 2 and len(min_p[2]) > 2:
                        if len(max_p[1]) > 0 and max_p[1][0] in min_p[1]:
                            can_check = False

                    elif len(max_p[2]) > 2 and len(min_p[2]) > 2:
                        for n in range(1, len(min_p[2]) -1):

                            if min_p[2][n] in max_p[2]:
                                can_check = False
                                break
                    else: can_check = False
                    if can_check:
                        check_weak_cycle(min_p, max_p, cycles)


def get_divergent_cycles(divergent, graph, cycles, rank, divergents_tps, convergents_tps):

    min_value = [0, [], [divergent], []] # value, contingents, time-points, requirement constraints
    max_value = [0, [], [divergent], []]

    min_path = {divergent: [min_value]}  # restrictive min path
    max_path = {divergent: [max_value]}  # restrictive max path

    path_to_redo = [max_value]

    while len(path_to_redo) > 0:  # max loop

        path = path_to_redo[0]
        path_to_redo.remove(path)
        last_tp = path[2][-1]

        for constraint in graph[last_tp]:

            dest = constraint.atoms[0].dest

            if is_path_Inner_cycle(dest, path, rank, divergents_tps) == False:

                new_path = max_new_path(path,constraint, dest)

                if dest in convergents_tps:

                    if dest not in max_path:

                        if len(new_path[1])==0:
                            max_path[dest] = [new_path]
                        else:
                            max_path[dest] = [None, new_path]
                        path_to_redo.append(new_path)

                    else:

                        add_max_path(new_path, max_path[dest], path_to_redo)
                else:
                    path_to_redo.append(new_path)

    path_to_redo = [min_value]

    while len(path_to_redo) > 0:  # max loop

        path = path_to_redo[0]
        path_to_redo.remove(path)
        last_tp = path[2][-1]

        for constraint in graph[last_tp]:

            dest = constraint.atoms[0].dest

            if is_path_Inner_cycle(dest, path, rank, divergents_tps) == False:

                new_path = min_new_path(path, constraint, dest)

                if dest in convergents_tps:

                    if dest not in min_path:

                        if len(new_path[1]) == 0:
                            min_path[dest] = [new_path]
                        else:
                            min_path[dest] = [None, new_path]
                        path_to_redo.append(new_path)

                    else:

                        add_min_path(new_path, min_path[dest], path_to_redo)
                else:
                    path_to_redo.append(new_path)


    check_cycles_controllaiblity(max_path, min_path, cycles)




def check_weak(problem):

    cycles = []
    graph, child_per_tp, divergents_tps, convergents_tps = get_divergent(problem) #child_per_tp is a map tp to constraints and divergents_tps is all tp that are divergent
    #print(child_per_tp)
    #print("divergent tp : ",divergents_tps)
    #print("tps: ",problem.timePoints)
    #print("convergent tps ", convergents_tps)
    rank = topological_ordering(child_per_tp, problem.vz)
    #print("rank ",rank)
    #exit(0)
    #print("size divergent_tp ", divergents_tps)

    for divergent in divergents_tps:
        #print(divergent)
        get_divergent_cycles(divergent, graph, cycles, rank, divergents_tps, convergents_tps)


    return cycles