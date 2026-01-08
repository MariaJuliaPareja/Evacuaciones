#!/usr/bin/python3
#
# v2

from agent import Agent
from io import BufferedWriter
import pickle

[Agent() for _ in range(5)]

# initialization 
Agent.instances[0].pos_x, Agent.instances[0].pos_y = (5, 5)
Agent.instances[1].pos_x, Agent.instances[1].pos_y = (3, 5)
Agent.instances[2].pos_x, Agent.instances[2].pos_y = (3, 5)
Agent.instances[3].pos_x, Agent.instances[3].pos_y = (5, 3)
Agent.instances[4].pos_x, Agent.instances[4].pos_y = (5, 3)

Agent.stores()

incr: int = 1
for it in range(10):
    Agent.instances[0].if_change = False
    
    Agent.instances[1].pos_x += incr
    Agent.instances[1].if_change = True
    Agent.instances[2].pos_x += -incr
    Agent.instances[2].if_change = True
    Agent.instances[3].pos_y += incr
    Agent.instances[3].if_change = True
    Agent.instances[4].pos_y += -incr
    Agent.instances[4].if_change = True

    Agent.stores()
    incr *= -1
    
size_x: int = 10
size_y: int = 10
list_obstacles: list[tuple[int]] = [(i, 0) for i in range(size_x)]
Agent.history.append({"size_x": size_x, "size_y": size_y, "obstacles": list_obstacles})
output: BufferedWriter = open("./historia.pkl", 'wb')
pickle.dump(Agent.history, output)
output.close()
