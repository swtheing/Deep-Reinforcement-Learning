
from Data_Generator.env_trj import *
from Data_Generator.env_trj.state_generator import *

class Greedy():
    def __init__(self, config, game_name, env):
        #model = Perceptron(game_name, None, config, "MSE", config.pre)
        #Reinforce_Suite.__init__(self, config, model, env)
        self.env = env

    def run_test(self, config):
        total_reward = 0.0
        total_episode = 0
        for i in range(0, 20):
            # greedy choose, every step chose one
            for taskid in self.env.simulator.pending_schedules:
                t_start_pos = self.env.simulator.pending_schedules[taskid][3][0:2]
                min_dis = -1.0
                for pid in self.env.simulator.participants:
                    if self.env.simulator.participants[pid][1] == ParticipantState["available"]:
                        p_start_pos = self.env.simulator.participants[pid][3]
                        distance = self.env.simulator.trajector.get_distance( \
                            t_start_pos[0], t_start_pos[1], p_start_pos[0], p_start_pos[1])
                        if distance < min_dis or min_dis < 0:
                            action_pid = pid
                            min_dis = distance
                action_task = taskid
                break
            action = ["pick", action_pid, action_task]
            observation, reward, done, info = self.env.step(action)
            if done:
                self.env.reset()
                total_episode += 1
                total_reward += reward
                print "episode: %d, reward: %s" % (total_episode, reward)
        ave_reward = total_reward / total_episode
        print "ave_reward: %s" % ave_reward


