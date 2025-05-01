# Multi-agent Interdependent Simple Temporal Networks under Uncertainty (MISTNU): The repair problem

Multi-Agent Interdependent Simple Temporal Networks under Uncertainty (MISTNU) extends the classical STNU framework to multi-agent contexts that fit decentralized multi-agent planning, where each agent plans its own course of action while coordinating through mutual commitments. In this model, the duration of certain constraints is determined by one agent but observed by others. In these scenarios, such constraints are considered contingent, according to STNU semantics. This gives rise to cases where some contingent durations are negotiable, meaning their intervals can be reduced in advance through coordination. The MISTNU model explicitly represents these constraints as contracts. For a detailed introduction to MISTNU, the reader is referred to the original paper: Ajdin Sumic, Thierry Vidal, Andrea Micheli, Alessandro Cimatti, Introducing Interdependent Simple Temporal Networks with Uncertainty for Multi-Agent Temporal Planning, TIME 2024.

An important aspect of the MISTNU framework is the notion of controllability, which varies depending on when the duration of a contract becomes available. Weak Controllability assumes that contract durations are revealed just before execution. Dynamic Controllability assumes they are observed during execution, possibly with limited foresight through oracles. Strong Controllability assumes that durations are never revealed or shared. Verifying controllability at any level in a MISTNU requires all individual agent networks to be controllable at that level.

When a MISTNU is not controllable, it is often possible to restore controllability by reducing the intervals of contract durations. This work introduces new centralized and distributed algorithms to repair MISTNUs that are not weakly controllable. These methods are part of a paper currently under review for ECAI 2025, and a citation will be provided once acceptance is confirmed.

In the following, we provide a concrete example of the MISTNU model and its repair problem by providing duration on the MISTNU that force it to not be weakly controllable.

# Example:

Consider a radiologist (agent a), a nurse (agent b), and a doctor (agent c). The radiologist must perform an X-ray on a patient, after which the doctor analyzes the results to prescribe medication. Meanwhile, the nurse waits for the X-ray to finish in order to escort the current patient to the waiting room and bring a second patient to the radiologist. This scenario involves three contracts: (p) the X-ray of the first patient, which is contingent for both the nurse and the doctor, (q) the nurse bringing the second patient to the radiologist, making it contingent for the radiologist, (r) the nurse waiting for the second X-ray to complete before moving the patient to another waiting room. After the second X-ray, the radiologist must clean and inspect the equipment as required by regulation. 


