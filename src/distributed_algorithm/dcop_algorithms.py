import subprocess
import json

def create_instance_file(file_path, mistnu, agent_cycles, map_contracts, contracts_variables):

    file = open(file_path + ".yaml", 'w')

    name = file_path.split("/")[-2:]
    name = "_".join(name)
    #print(name)

    file.write("name: "+name+"\n")
    file.write("objective: min\n" )
    file.write("\n")
    generate_domains_field(file, mistnu)
    generate_variables_field(file, mistnu, contracts_variables)
    generate_constraint_field(file, mistnu, contracts_variables, agent_cycles, map_contracts)
    generate_agents_field(file, contracts_variables)
    generate_distribution_hints_field(file, contracts_variables)

def generate_agents_field(file, contracts_variables):

    file.write("agents:\n")

    for name, (l, u) in contracts_variables.items():

        file.write("  A_" + l + ":\n")
        file.write("    capacity: 100000\n")
        file.write("  A_" + u + ":\n")
        file.write("    capacity: 100000\n")
    file.write("\n")

def generate_distribution_hints_field(file, contracts_variables):
    file.write("distribution_hints:\n")
    file.write("  must_host:\n")

    for name, (l, u) in contracts_variables.items():
        file.write("    A_" + l + ": [" + l + "]\n")
        file.write("    A_" + u + ": [" + u + "]\n")
    file.write("\n")

def generate_domains_field(file, mistnu):

    file.write("domains:\n")
    file.write("\n")
    for name, values in mistnu.B.items():
        (l,u) = values[0]
        file.write("  "+ name +"_domain:\n")

        domains_values = [i for i in range(l,u+1)]
        file.write("    values: "+str(domains_values)+"\n")
        file.write("    type: 'time-unit'\n")
        file.write("\n")

def generate_variables_field(file, mistnu, contracts_variables):

    file.write("variables:\n")

    for name, (l,u) in contracts_variables.items():

        file.write("  "+ l +":\n")
        file.write("    domain: "+ name +"_domain\n")
        file.write("    cost_function: "+ l +" - "+str(mistnu.B[name][0][0])+ "\n")

        file.write("\n")

        file.write("  " + u + ":\n")
        file.write("    domain: " + name + "_domain\n")
        file.write("    cost_function: " + str(mistnu.B[name][0][1]) + " - "+ u +"\n")

    file.write("\n")

def generate_constraint_field(file, mistnu, contracts_variables, agent_cycles, map_contracts):
    file.write("constraints:\n")

    generate_variable_constraint_field(file, contracts_variables)
    generate_cycles_constraint_field(file, mistnu, contracts_variables, agent_cycles, map_contracts)
    file.write("\n")

def generate_variable_constraint_field(file, contracts_variables):

    for name, (l,u) in contracts_variables.items():
        file.write("  diff_"+ l +"_"+ u +":\n")
        file.write("    type: intention\n")
        file.write("    function: 100000 if " + l + " > "+ u + " else 0\n")
        file.write("\n")
    file.write("\n")

def generate_min_path_formula(contracts, map_contracts,contracts_variables, paths_formula):
    for contingent in contracts:
        if contingent.contract:
            source = contingent.atoms[0].source.name
            dest = contingent.atoms[0].dest.name
            l = contingent.atoms[0].lowerBound
            u = contingent.atoms[0].upperBound

            if l<0: # if inverse contingent then l and u are inversed
                contract_variable = contracts_variables[map_contracts[dest+"_"+source]][0]
                paths_formula.append(contract_variable + " - "+ str((u*-1)))

            else:
                contract_variable = contracts_variables[map_contracts[source+"_"+dest]][1]
                paths_formula.append(str(u) + " - " + contract_variable)





def generate_max_path_formula(contracts, map_contracts,contracts_variables, paths_formula):

    for contingent in contracts:
        if contingent.contract:
            source = contingent.atoms[0].source.name
            dest = contingent.atoms[0].dest.name
            l = contingent.atoms[0].lowerBound
            u = contingent.atoms[0].upperBound


            if l < 0:  # if inverse contingent then l and u are inversed
                contract_variable = contracts_variables[map_contracts[dest+"_"+source]][1]
                paths_formula.append(str((l*-1)) + " - " + contract_variable)



            else:
                contract_variable = contracts_variables[map_contracts[source+"_"+dest]][0]
                paths_formula.append( contract_variable + " - " + str(l))



def generate_cycle_formula(cycle, map_contracts,contracts_variables):
    min_p = cycle[0]
    max_p = cycle[1]

    flexibility = min_p[0] - max_p[0]

    paths_formula = []

    # min_path
    min_formula = generate_min_path_formula(min_p[1], map_contracts,contracts_variables, paths_formula)
    max_formula = generate_max_path_formula(max_p[1], map_contracts,contracts_variables, paths_formula)

    paths_formula = " + ".join(paths_formula)

    return "(" + paths_formula + ") >= " + str(flexibility)

def generate_cycles_constraint_field(file, mistnu, contracts_variables, agent_cycles, map_contracts):
    print(agent_cycles)
    print("////////")
    print(map_contracts)

    for agent, cycles in agent_cycles.items():
        for i,cycle in enumerate(cycles):
            cycle_formula = generate_cycle_formula(cycle, map_contracts, contracts_variables)
            cycle_name = agent+"_cycle_"+str(i) +":"
            file.write("  " + cycle_name + "\n")
            file.write("    type: intention\n")
            file.write("    function: 0 if " + cycle_formula + " else 100000\n")
            file.write("\n")


def create_contracts_variables(mistnu):
    contracts_variables = {}
    for name, values in mistnu.B.items():
        (l,u) = values[0]
        variable_l = name+"_l"
        variable_u = name+"_u"
        contracts_variables[name] = (variable_l,variable_u)
    return contracts_variables


def run_dpop(mistnu, agent_cycles, map_contracts, inputFile):

    name = inputFile.split("/")[-1]
    name = name.split(".")[0]

    file_path = "/".join(inputFile.split("/")[0:-1])
    file_path+= "/benchmark_dcop/"+name

    contracts_variables = create_contracts_variables(mistnu)

    create_instance_file(file_path, mistnu, agent_cycles, map_contracts, contracts_variables)

    bash_command = ["pydcop", "--output", file_path +".json", "solve", "--algo", "dpop", file_path +".yaml"]
    subprocess.call(bash_command)

    result = json.load(open(file_path +".json"))
    print("Failed as it did not satisfy a constraints") if int(result["cost"]) > 100000 else print("A repair has been found !")


def run_syncbb(mistnu, agent_cycles, map_contracts, inputFile):

    name = inputFile.split("/")[-1]
    name = name.split(".")[0]

    file_path = "/".join(inputFile.split("/")[0:-1])
    file_path+= "/benchmark_dcop/"+name

    contracts_variables = create_contracts_variables(mistnu)

    create_instance_file(file_path, mistnu, agent_cycles, map_contracts, contracts_variables)

    bash_command = ["pydcop", "--output", file_path +".json", "solve", "--algo", "dpop", file_path +".yaml"]
    subprocess.call(bash_command)

    result = json.load(open(file_path +".json"))
    print("Failed as it did not satisfy a constraints") if int(result["cost"]) > 100000 else print("A repair has been found !")

