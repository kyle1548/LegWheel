import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Circle
from matplotlib.animation import FuncAnimation
import PlotLeg
import LegModel
from utils import *
import sys
sys.path.append('bezier')
import swing

leg_model = LegModel.LegModel(sim=True)

# User-defined parameters #
animate = True  # create animate file
output_file_name = 'walk_trajectory'
BL = 0.444  # body length, 44.4 cm
BH = 0.2     # body height, 20 cm
CoM_bias = 0.0    # x bias of center of mass
velocity = 0.2     # velocity of hip, meter per second
sampling = 400            # sampling rate, how many commands to one motor per second.
stand_height = 0.25 + leg_model.r
step_length = 0.4
step_height = 0.04
forward_distance = 2.0  # distance to walk

# Dependent parameters #
swing_time = 0.2    # duty: 0.8~1.0
duty = np.array([1-swing_time, 0.5-swing_time, 0.5, 0.0])   # initial duty, left front leg first swing
# duty = np.array([0.5-swing_time, 1-swing_time, 0.0, 0.5])   # initial duty, right front leg first swing
swing_phase = np.array([0, 0, 0, 0]) # initial phase, 0:stance, 1:swing
hip = np.array([[BL/2, stand_height],
                [BL/2, stand_height],
                [-BL/2, stand_height],
                [-BL/2, stand_height]])
foothold = np.array([hip[0] + [-step_length/2*(1-swing_time), -stand_height],
                    hip[0] + [step_length/8*(1-swing_time), -stand_height],
                    hip[2] + [-step_length/8*(1-swing_time), -stand_height],
                    hip[2] + [step_length/2*(1-swing_time), -stand_height]])
foothold += np.array([[CoM_bias, 0]])
dS = velocity/sampling    # hip traveling distance per one sample
incre_duty = dS / step_length

#### Walk ####
# Initial stored data
theta_list = [[] for _ in range(4)]
beta_list = [[] for _ in range(4)]
hip_list = [[] for _ in range(4)]
swing_length_arr = [[] for _ in range(4)]
swing_angle_arr = [[] for _ in range(4)]
sp = [[] for _ in range(4)]
traveled_distance = 0

# Initial teata, beta
contact_rim = ["G", "Ll", "Lr", "Ul", "Ur"]
rim_idx =   [3  , 2   , 4   , 1   , 5]
contact_hieght = [leg_model.r, leg_model.radius, leg_model.radius, leg_model.radius, leg_model.radius]
for i in range(4):
    # calculate contact rim of initial pose
    for j in range(5):
        theta, beta = leg_model.inverse(foothold[i]+np.array([0, contact_hieght[j]]) - hip[i], contact_rim[j])
        leg_model.contact_map(theta, beta)
        if leg_model.rim == rim_idx[j]:
            break
    theta_list[i].append(theta)
    beta_list[i].append(beta)
    hip_list[i].append(hip[i].copy())
    
# Start walking
while traveled_distance <= forward_distance:
    for i in range(4):
        if swing_phase[i] == 0: # stance phase     
            theta, beta = leg_model.move(theta_list[i][-1], beta_list[i][-1], hip[i] - hip_list[i][-1])
        else:   # swing phase     
            swing_phase_ratio = (duty[i]-(1-swing_time))/(swing_time)
            curve_point = sp[i].getFootendPoint(swing_phase_ratio) # G position in world coordinate
            theta, beta = leg_model.inverse(curve_point - hip[i], 'G')
        theta_list[i].append(theta)
        beta_list[i].append(beta)
        hip_list[i].append(hip[i].copy())
        
        duty[i] += incre_duty
        if duty[i] >= (1-swing_time) and swing_phase[i] == 0:
            swing_phase[i] = 1
            foothold[i] = [hip[i][0], 0] + ((1-swing_time)/2+swing_time)*np.array([step_length, 0])
            # Bezier curve for swing phase
            p_lo = hip[i] + leg_model.G # G position when leave ground
            # calculate contact rim when touch ground
            for j in [0, 1, 3]: # G, Ll, Rl
                theta, beta = leg_model.inverse( np.array([step_length/2*(1-swing_time), -stand_height+contact_hieght[j]]), contact_rim[j])
                leg_model.contact_map(theta, beta)  # also get joint positions when touch ground, in polar coordinate (x+jy).
                if leg_model.rim == rim_idx[j]:
                    touch_rim = leg_model.rim
                    break
            # G position when touch ground
            if touch_rim == 3:  # G
                p_td = foothold[i] + np.array([0, leg_model.r])
            elif touch_rim == 2:  # L_l
                p_td = foothold[i] + np.array([0, leg_model.radius]) + [leg_model.G.real-leg_model.L_l.real, leg_model.G.imag-leg_model.L_l.imag]
            elif touch_rim == 1:  # U_l
                p_td = foothold[i] + np.array([0, leg_model.radius]) + [leg_model.G.real-leg_model.U_l.real, leg_model.G.imag-leg_model.U_l.imag]
            sp[i] = swing.SwingProfile(p_td[0] - p_lo[0], step_height, 0.0, 0.0, 0.0, 0.0, 0.0, p_lo[0], p_lo[1], p_td[1] - p_lo[1])
        elif duty[i] >= 1.0:
            swing_phase[i] = 0
            duty[i] -= 1.0

        hip[i] += [dS, 0]
    traveled_distance += dS

theta_list = np.array(theta_list)
beta_list = np.array(beta_list)
hip_list = np.array(hip_list)
create_command_csv(theta_list, -beta_list, output_file_name, transform=False)

if animate:
    fps = 10
    divide = sampling//fps
    fig_size = 10
    fig, ax = plt.subplots( figsize=(fig_size, fig_size) )

    Animation = PlotLeg.LegAnimation()
    Animation.setting()
        
    number_command = theta_list.shape[1]
    def plot_update(frame):
        global ax
        ax.clear()  # clear plot
        
        #### Plot ####
        ax.set_aspect('equal')  # 座標比例相同
        ax.set_xlim(-0.5, 1.0)
        ax.set_ylim(-0.1, 0.5)
        
        # Ground
        # Whole Terrain
        plt.plot([-0.5, 1], [0, 0], 'g-') # hip trajectory on the stair
        plt.grid(True)
        
        
        plt.plot(*(( hip_list[0, frame*divide]+ hip_list[2, frame*divide])/2), 'P', color="orange", ms=10, mec='k') # center of mass    
        for i in range(4):
            ax = Animation.plot_one(theta_list[i, frame*divide], beta_list[i, frame*divide], hip_list[i, frame*divide, :], ax)

    ani = FuncAnimation(fig, plot_update, frames=number_command//divide)
    ani.save(output_file_name + ".mp4", fps=fps)

    
    