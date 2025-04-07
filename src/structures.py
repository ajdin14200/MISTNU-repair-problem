# Problem structures
import math
import sys

from errors import *



class TimePoint(object):

    def __init__(self, name, controllable):
        self.name = name
        self.controllable = controllable
        return

    pass



class AtomicConstraint(object):

    def __init__(self, source, dest, lower, upper):

        if self.checkValue(lower, False) and self.checkValue(upper, True):
            self.source = source
            self.dest = dest
            self.lowerBound = lower
            self.upperBound = upper
        else:
            raise MalformationError()

        return


    def checkValue(self, v, upper):
        if isinstance(v, str):
            if 'inf' not in v:
                return True
            else:
                return (upper and (v == "+inf")) or \
                    ((not upper) and (v == "-inf"))
        else:
            return isinstance(v, float) or isinstance(v, int)

        assert False
        return False

    def __str__(self):
        return ("(%s - %s) in [%s, %s]" % \
                    (self.dest.name, self.source.name,
                     str(self.lowerBound), str(self.upperBound)))

    pass

class Agent(object):
    def __init__(self, name):
        self.name  = name

# This class represent the MISTNU class
class MAS(object):

    def __init__(self):
        self.agents = []    # A is a set of agent
        self.problems = []   # S a set if temporal network
        self.B = {}          # B the map of process to bound
        self.readers = {}    # R a map of agent to a list of process it reads
        self.owners = {}    # O a map of agent to a list of process it write

    def encode_tn_from_file(self, entries, pointer, tn, agent_process, agent):

        nn = int(entries[pointer])
        ne = int(entries[pointer+1])
        label = None
        pointer = pointer + 2
        for i in range(0, nn):
            name = entries[pointer]
            cflag = entries[pointer + 1]

            tn.createTimePoint(tn.fixName(name), (cflag == "c"))
            pointer = pointer + 2

        for i in range(0, ne):
            ndisjunction = int(entries[pointer])

            cflag = entries[pointer + 1]
            contingent = (cflag == "c")
            process = False

            pointer = pointer + 2

            atoms = set()
            for _ in range(0, ndisjunction):
                s = tn.getTimePoint(tn.fixName(entries[pointer]))
                d = tn.getTimePoint(tn.fixName(entries[pointer + 1]))

                l = entries[pointer + 2]
                u = entries[pointer + 3]



                try:
                    if u in self.B and l in self.B:
                        process = True
                        label = u
                    else:
                        if u != "+inf" and u != "-inf":
                            #u = float(u)
                            u = int(u)

                        if l != "+inf" and l != "-inf":
                            #l = float(l)
                            l = int(l)
                except Exception:
                    raise ParsingError("Expected float number or infinity keywords", nn + i + 1)

                at = None
                try:
                    at = AtomicConstraint(s, d, l, u)
                except MalformationError:
                    raise

                if at is not None:
                    atoms.add(at)

                pointer = pointer + 4

            if len(atoms) == 0:
                raise TriviallyInconsistentError("All the constraints in line %d are trivially false" % i)

            c = tn.createConstraint(atoms, contingent, process)
            if process:
                if agent_process[label] == agent.name:
                    self.owners[agent_process[label]].append(c)




        return pointer

    def fromFile(self, filename):
        f = open(filename, "rt")
        entries = f.read().split()
        agent_process = {}
        number_agent = int(entries[0])
        for i in range(1, number_agent + 1):
            agent = Agent(entries[i])
            self.agents.append(agent)


        pointer = number_agent + 1  # next line
        number_process = int(entries[pointer])
        for i in range(1, number_process + 1):
            self.B[entries[pointer + i]] = []
            self.readers[entries[pointer + i]] = []

        pointer = pointer + number_process + 1  # next line
        for line in range(number_process):
            process_label = entries[pointer]
            process_bounds = [int(entries[pointer + 1]), int(entries[pointer + 2])]
            process_owner = entries[pointer + 4]
            number_readers = int(entries[pointer + 5])
            process_readers = []
            pointer = pointer + 5
            self.owners[process_owner] = []
            agent_process[process_label] = process_owner
            for reader in range(1, number_readers + 1):
                process_readers.append(entries[pointer + reader])
            self.B[process_label].append(process_bounds)
            self.readers[process_label] = process_readers
            pointer = pointer + reader + 1

        for i in range(number_agent):
            tn = Problem()
            agent = self.agents[i]
            pointer = self.encode_tn_from_file(entries, pointer, tn, agent_process, agent)
            self.problems.append(tn)



class Constraint(object):

    def __init__(self, atoms, contingent=False, process=False, fixBin=False):
        self.atoms = list(atoms)
        self.contingent = contingent
        self.process = process # this will help in recognizing a constraint which is a process

        if fixBin and len(atoms) > 1:
            self.fixBinary()

        return

    def isBinary(self):
        s = None
        d = None

        for a in self.atoms:
            if s is None and d is None:
                s = a.source
                d = a.dest
                assert s is not None
                assert d is not None
            else:
                if a.source != s or a.dest != d:
                    return False

        return True


    def fixBinary(self):
        s = None
        d = None

        for a in self.atoms:
            if s is None and d is None:
                s = a.source
                d = a.dest
                assert s is not None
                assert d is not None
            else:
                if a.source == d and a.dest == s:
                    tmp = a.source
                    a.source = a.dest
                    a.dest = tmp

                    l = a.lowerBound
                    u = a.upperBound

                    if l != 0 and u != 0:
                        if l == -math.inf:
                            a.upperBound = math.inf
                        else:
                            a.upperBound = -1 * l

                            if u == math.inf:
                                a.lowerBound = -math.inf
                            else:
                                a.lowerBound = -1 * u
        return

    pass



class DisjunctivityLevel(object):

    (NONE, BINARY, FULL) = range(0,3)

    pass



class Problem(object):

    def __init__(self):
        self.timePoints = {}
        self.constraints = set()
        self.contingent_parent = {}
        self.vz = None

        self.positive = True
        self.disjunctivity = DisjunctivityLevel.NONE
        self.game = False
        return


    def createTimePoint(self, name, controllable):
        if not controllable:
            self.game = True

        if type(name) is int:
            name = ("X%d" % name)

        if name in self.timePoints:
            raise RedefinitionError()

        n = TimePoint(name, controllable)
        if len(self.timePoints) == 0:
            self.vz = n
        self.timePoints[name] = n

        return n


    def getTimePoint(self, name):
        if type(name) is int:
            name = ("X%d" % name)

        if name in self.timePoints:
            return self.timePoints[name]
        raise NoSuchElementError()


    def createConstraint(self, atoms, contingent=False, process=False, fixBinary=False):
        assert len(atoms) > 0;

        c = Constraint(atoms, contingent,process, fixBinary)
        self.constraints.add(c)

        if c.contingent:
            assert c.isBinary()
            s = c.atoms[0].source
            d = c.atoms[0].dest
            self.contingent_parent[d] = s

        if len(atoms) > 1:
            # at least binary
            if self.disjunctivity != DisjunctivityLevel.FULL:
                if c.isBinary():
                    self.disjunctivity = DisjunctivityLevel.BINARY
                else:
                    self.disjunctivity = DisjunctivityLevel.FULL

        for a in atoms:
            if isinstance(a.lowerBound, str):
                if a.lowerBound == "-inf":
                    self.positive = False
                    break
            elif a.lowerBound < 0:
                self.positive = False
                break

            if isinstance(a.upperBound, str):
                if a.upperBound != "+inf" :
                    self.positive = False
                    break
            elif a.upperBound < 0:
                self.positive = False
                break

        return c


    def getDensity(self):
        e = len(self.constraints)
        v = len(self.timePoints)
        return (float(2 * e) / float(v * (v - 1)))


    def compress(self):
        used = set()
        for c in self.constraints:
            for a in c.atoms:
                used.add(a.source)
                used.add(a.dest)

        todel = []
        for n in self.timePoints.values():
            if n not in used:
                todel.append(n)

        for p in todel:
            del self.timePoints[p.name]

        return


    def toFile(self, stream=sys.stdout):
        '''Print in AMI format'''

        stream.write("%d %d\n" % (len(self.timePoints), len(self.constraints)))

        for n in self.timePoints.values():
            stream.write("%s " % n.name)
            if n.controllable:
                stream.write("c\n")
            else:
                stream.write("u\n")

        for c in self.constraints:
            cons = "f"
            if c.contingent:
                cons = "c"
            if c.process:
                cons = "p"

            stream.write("%d %s " % (len(c.atoms), cons))

            for a in c.atoms:
                s = a.source.name
                d = a.dest.name
                l = str(a.lowerBound)
                u = str(a.upperBound)

                stream.write("%s %s %s %s " % (s, d, l, u))

            stream.write("\n")
        return

    def fixName(self, name):
        return name
        return name.replace("_","__").replace(".", "_");



    def printDot(self, stream=sys.stdout):
        '''Prints the given network in DOT format'''

        if self.disjunctivity == DisjunctivityLevel.FULL:
            raise UnsupportedError()


        stream.write("digraph {\n");

        for v in self.timePoints.values():
            cs = ""
            if not v.controllable:
                cs = "double"

            stream.write("node [shape=%scircle] \"%s\";\n" % (cs, v.name))

        stream.write("\n")


        for c in self.constraints:
            s = c.atoms[0].source.name
            d = c.atoms[0].dest.name

            style = "dashed"
            atype = "empty"
            if c.contingent:
                style = "solid"
                atype = "normal"

            stream.write(("\"%s\" -> \"%s\" [ arrowhead=\"%s\", style=\"%s\", label = \"" %
                          (s, d, atype, style)))


            count = 0
            for a in c.atoms:
                l = a.lowerBound
                u = a.upperBound

                stream.write("[")
                stream.write(str(l))
                stream.write(", ")
                stream.write(str(u))
                stream.write("]")

                count = count + 1
                if count < len(c.atoms):
                    stream.write(" | ")

            stream.write("\"];\n")


        stream.write("\n")
        stream.write("}\n");
        return

    pass



class Interval(object):

    def __init__(self, name, bounds, contingent):
        if type(name) is int:
            name = ("X%d" % name)

        self.name = name
        self.bounds = bounds
        self.contingent = contingent
        return

    pass



class AllenRelation(object):

    (BEFORE,AFTER,STARTS,STARTED_BY,FINISHES,FINISHED_BY,MEETS,MET_BY,DURING,CONTAINED,OVERLAPS,OVERLAPPED_BY,EQUAL, S_E, E_S, S_S, E_E) = range(0,17)

    def __init__(self, source, dest, typeid, bounds):
        self.source = source
        self.dest = dest
        self.typeid = typeid
        self.bounds = bounds
        return

    pass


class AllenConstraint(object):

    def __init__(self, relations):
        self.relations = list(relations)
        return

    def isBinary(self):
        s = None
        d = None

        for a in self.relations:
            if s is None and d is None:
                s = a.source
                d = a.dest
                assert s is not None
                assert d is not None
            else:
                if a.source != s or a.dest != d:
                    return False
        return True

    pass



class IntervalProblem(object):

    def __init__(self):
        self.intervals = {}
        self.constraints = []
        return


    def createInterval(self, name, bounds, contingent):
        if name in self.intervals:
            raise RedefinitionError()
        else:
            n = Interval(name, bounds, contingent)
            self.intervals[name] = n
            return n


    def getInterval(self, name):
        if name in self.intervals:
            return self.intervals[name]
        else:
            raise NoSuchElementError()


    def createConstraint(self,relations):
        c = AllenConstraint(relations)
        self.constraints.append(c)
        return c


    def getDensity(self):
        e = len(self.constraints)
        v = len(self.intervals)
        return (float(2 * e) / float(v * (v - 1)))

    pass



class IntervalConverter(object):

    def __init__(self, intervalProblem, fixBinary=False):
        self.problem = intervalProblem

        self.interval2start = {}
        self.interval2end = {}

        self.fixBinary = fixBinary
        return


    def getProblem(self):
        res = Problem()

        # create time points
        for i in self.problem.intervals.values():
            s = res.createTimePoint(i.name + "_start", True)
            e = res.createTimePoint(i.name + "_end", not i.contingent)

            self.interval2start[i] = s
            self.interval2end[i] = e

            disj = [AtomicConstraint(s, e, l, u) for (l,u) in i.bounds]
            res.createConstraint(disj, i.contingent)


        for c in self.problem.constraints:
            disj = []
            for r in c.relations:
                disj.append(self.convertRelation(r))


            cnf = []
            for d in disj:
                if cnf == []:
                    for a in d:
                        cnf.append([a])
                else:
                    tmp = []
                    for a in d:
                        for c in cnf:
                            nc = list(c)
                            nc.append(a)
                            tmp.append(nc)
                    cnf = tmp

            for c in cnf:
                res.createConstraint(c, False, self.fixBinary)


        return res


    def convertRelation(self, r):
        # results = []
        # if r.typeid == AllenRelation.BEFORE:
        #     results.append(AtomicConstraint(self.interval2end[r.source], self.interval2start[r.dest], r.bounds[0], r.bounds[1]))
        # elif r.typeid == AllenRelation.AFTER:
        #     results.append(AtomicConstraint(self.interval2end[r.dest], self.interval2start[r.source], r.bounds[0], r.bounds[1]))
        # elif r.typeid == AllenRelation.STARTS:
        #     results.append(AtomicConstraint(self.interval2start[r.source], self.interval2start[r.dest], 0, 0))
        # elif r.typeid == AllenRelation.STARTED_BY:
        #     results.append(AtomicConstraint(self.interval2start[r.dest], self.interval2start[r.source], 0, 0))
        # elif r.typeid == AllenRelation.FINISHES:
        #     results.append(AtomicConstraint(self.interval2end[r.source], self.interval2end[r.dest], 0, 0))
        # elif r.typeid == AllenRelation.FINISHED_BY:
        #     results.append(AtomicConstraint(self.interval2end[r.dest], self.interval2end[r.source], 0, 0))
        # elif r.typeid == AllenRelation.MEETS:
        #     results.append(AtomicConstraint(self.interval2end[r.source], self.interval2start[r.dest], 0, 0))
        # elif r.typeid == AllenRelation.MET_BY:
        #     results.append(AtomicConstraint(self.interval2end[r.dest], self.interval2start[r.source], 0, 0))
        # elif r.typeid == AllenRelation.DURING:
        #     results.append(AtomicConstraint(self.interval2start[r.dest], self.interval2start[r.source], r.bounds[0], r.bounds[1]))
        #     results.append(AtomicConstraint(self.interval2end[r.source], self.interval2end[r.dest], r.bounds[2], r.bounds[3]))
        # elif r.typeid == AllenRelation.CONTAINED:
        #     results.append(AtomicConstraint(self.interval2start[r.source], self.interval2start[r.dest], r.bounds[0], r.bounds[1]))
        #     results.append(AtomicConstraint(self.interval2end[r.dest], self.interval2end[r.source], r.bounds[2], r.bounds[3]))
        # elif r.typeid == AllenRelation.OVERLAPS:
        #     results.append(AtomicConstraint(self.interval2start[r.dest], self.interval2end[r.source], r.bounds[0], r.bounds[1]))
        #     results.append(AtomicConstraint(self.interval2end[r.source], self.interval2end[r.dest], 0, math.inf))
        # elif r.typeid == AllenRelation.OVERLAPPED_BY:
        #     results.append(AtomicConstraint(self.interval2start[r.source], self.interval2end[r.dest], r.bounds[0], r.bounds[1]))
        #     results.append(AtomicConstraint(self.interval2end[r.dest], self.interval2end[r.source], 0, math.inf))
        # elif r.typeid == AllenRelation.EQUAL:
        #     results.append(AtomicConstraint(self.interval2start[r.source], self.interval2start[r.dest], 0, 0))
        #     results.append(AtomicConstraint(self.interval2end[r.source], self.interval2end[r.dest], 0, 0))
        # else:
        #     assert False, ("Typeod cannot be  %d" % r.typeid)


        res = []
        if r.typeid == AllenRelation.BEFORE:
            res.append(AtomicConstraint(self.interval2end[r.source], self.interval2start[r.dest], 0, math.inf))
        elif r.typeid == AllenRelation.AFTER:
            res.append(AtomicConstraint(self.interval2end[r.dest], self.interval2start[r.source], 0, math.inf))
        elif r.typeid == AllenRelation.STARTS:
            res.append(AtomicConstraint(self.interval2start[r.source], self.interval2start[r.dest], 0, 0))
        elif r.typeid == AllenRelation.STARTED_BY:
            res.append(AtomicConstraint(self.interval2start[r.dest], self.interval2start[r.source], 0, 0))
        elif r.typeid == AllenRelation.FINISHES:
            res.append(AtomicConstraint(self.interval2end[r.source], self.interval2end[r.dest], 0, 0))
        elif r.typeid == AllenRelation.FINISHED_BY:
            res.append(AtomicConstraint(self.interval2end[r.dest], self.interval2end[r.source], 0, 0))
        elif r.typeid == AllenRelation.MEETS:
            res.append(AtomicConstraint(self.interval2end[r.source], self.interval2start[r.dest], 0, 0))
        elif r.typeid == AllenRelation.MET_BY:
            res.append(AtomicConstraint(self.interval2end[r.dest], self.interval2start[r.source], 0, 0))
        elif r.typeid == AllenRelation.DURING:
            res.append(AtomicConstraint(self.interval2start[r.dest], self.interval2start[r.source], 0, math.inf))
            res.append(AtomicConstraint(self.interval2end[r.source], self.interval2end[r.dest], 0, math.inf))
        elif r.typeid == AllenRelation.CONTAINED:
            res.append(AtomicConstraint(self.interval2start[r.source], self.interval2start[r.dest], 0, math.inf))
            res.append(AtomicConstraint(self.interval2end[r.dest], self.interval2end[r.source], 0, math.inf))
        elif r.typeid == AllenRelation.OVERLAPS:
            res.append(AtomicConstraint(self.interval2start[r.dest], self.interval2end[r.source], 0, math.inf))
            res.append(AtomicConstraint(self.interval2end[r.source], self.interval2end[r.dest], 0, math.inf))
        elif r.typeid == AllenRelation.OVERLAPPED_BY:
            res.append(AtomicConstraint(self.interval2start[r.source], self.interval2end[r.dest], 0, math.inf))
            res.append(AtomicConstraint(self.interval2end[r.dest], self.interval2end[r.source], 0, math.inf))
        elif r.typeid == AllenRelation.EQUAL:
            res.append(AtomicConstraint(self.interval2start[r.source], self.interval2start[r.dest], 0, 0))
            res.append(AtomicConstraint(self.interval2end[r.source], self.interval2end[r.dest], 0, 0))


        # Magic relations
        elif r.typeid == AllenRelation.S_S:
            res.append(AtomicConstraint(self.interval2start[r.source], self.interval2start[r.dest],  r.bounds[0], r.bounds[1]))
        elif r.typeid == AllenRelation.S_E:
            res.append(AtomicConstraint(self.interval2start[r.source], self.interval2end[r.dest],  r.bounds[0], r.bounds[1]))
        elif r.typeid == AllenRelation.E_S:
            res.append(AtomicConstraint(self.interval2end[r.source], self.interval2start[r.dest],  r.bounds[0], r.bounds[1]))
        elif r.typeid == AllenRelation.E_E:
            res.append(AtomicConstraint(self.interval2end[r.source], self.interval2end[r.dest],  r.bounds[0], r.bounds[1]))

        else:
            assert False, ("Typeid cannot be  %d" % r.typeid)

        return res
