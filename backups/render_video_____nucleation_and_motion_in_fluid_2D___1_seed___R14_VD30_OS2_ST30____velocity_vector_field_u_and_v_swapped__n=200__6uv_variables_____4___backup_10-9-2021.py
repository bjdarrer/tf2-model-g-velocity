from __future__ import division

import argparse
import numpy as np
import tensorflow as tf
import progressbar
import imageio
import yaml
import matplotlib.pyplot as pp  # BJD added 18.11.2020
#import cv2 # BJD added 24.11.2020 - for make video
#import glob # BJD added 24.11.2020 - for make video
#import matplotlib.pyplot as plt
#import ffmpeg
import os # BJD added 24.11.2020 - for make video

import io # BJD added 18.11.2020
try:
    from yaml import CLoader as Loader
except ImportError:
    from yaml import Loader

from model_g import ModelG
from fluid_model_g import FluidModelG
from util import bl_noise
from numpy import * # BJD added 20.11.2020
from matplotlib import pyplot as plt # BJD added 20.11.2020
from scipy import signal # BJD added 23.12.2020


RESOLUTIONS = {
    "2160p": (3840, 2160),
    "1440p": (2560, 1440),
    "1080p": (1920, 1080),
    "720p": (1280, 720),
    "480p": (854, 480),
    "360p": (640, 360),
    "240p": (426, 240),
    "160p": (284, 160),
    "80p": (142, 80),
    "40p": (71, 40),
}


def make_video_frame(rgb, indexing='ij'):
    if indexing == 'ij':
        rgb = [tf.transpose(channel) for channel in rgb]
    frame = tf.stack(rgb, axis=-1)
    frame = tf.clip_by_value(frame, 0.0, 1.0)
    return tf.cast(frame * 255, 'uint8').numpy()


def nucleation_and_motion_in_G_gradient_fluid_2D(writer, args, R=14):
    c1 = 0 # BJD added this on 10.9.2021
    dx = 2*R / args.height
    x = (np.arange(args.width) - args.width // 2) * dx
    y = (np.arange(args.height) - args.height // 2) * dx
    x, y = np.meshgrid(x, y, indexing='ij')

    def source_G(t):
        center = np.exp(-0.5*(t-5)**2) * 10
        gradient = (1+np.tanh(t-30)) * 0.0003
        return -np.exp(-0.5*(x*x+y*y))* center + (x+8) * gradient

    source_functions = {
        'G': source_G,
    }

    flow = [0*x, 0*x] # BJD original 10-9-2021
    #flow = [0*x, 0*x, 0*x, 0*x, 0*x, 0*x] # BJD added 10-9-2021

    fluid_model_g = FluidModelG(
        x*0,
        x*0,
        x*0,
        flow,
        dx,
        dt=args.dt,
        params=args.model_params,
        source_functions=source_functions,
    )

    print("Rendering 'Nucleation and Motion in G gradient in 2D'")
    print("Lattice constant dx = {}, time step dt = {}".format(fluid_model_g.dx, fluid_model_g.dt))
    min_G = -4.672736908320116
    max_G = 0.028719261862332906
    min_X = -3.8935243721220334
    max_X = 1.2854028081816122
    min_Y = -0.7454193158963579
    max_Y = 4.20524950766914
    for n in progressbar.progressbar(range(args.num_frames)):
        fluid_model_g.step()
        if n % args.oversampling == 0:
            rgb = [
                6*(-fluid_model_g.G + max_G) / (max_G - min_G),
                5*(fluid_model_g.Y - min_Y) / (max_Y - min_Y),
                0.7*(fluid_model_g.X - min_X) / (max_X - min_X),
            ]
            zero_line = 1 - tf.exp(-600 * fluid_model_g.Y**2)
            frame = make_video_frame([c * zero_line for c in rgb])
            writer.append_data(frame)
    #     max_G = max(max_G, tf.reduce_max(fluid_model_g.G).numpy())
    #     min_G = min(min_G, tf.reduce_min(fluid_model_g.G).numpy())
    #     max_X = max(max_X, tf.reduce_max(fluid_model_g.X).numpy())
    #     min_X = min(min_X, tf.reduce_min(fluid_model_g.X).numpy())
    #     max_Y = max(max_Y, tf.reduce_max(fluid_model_g.Y).numpy())
    #     min_Y = min(min_Y, tf.reduce_min(fluid_model_g.Y).numpy())

    # print(min_G, max_G, min_X, max_X, min_Y, max_Y)
#-------------------------BJD 28.1.2021----rough code at present-----------------------------------------
            
            if n == 200:
                print("n = ", n)
                break
            print("H E L L O")

            c1 = c1 + 1
            #nx, ny = 256, 1024
            nx, ny = 240, 426
            #(426,240)
            x1 = range(nx)
            y1 = range(ny)
            """
            #data = numpy.random.random((nx, ny))
            # swapped U and V around - BJD 3.9.2021
            U = np.loadtxt("/home/brendan/software/tf2-model-g-velocity/arrays/quiver_array1/v.txt") #, delimiter=" :-) ", usecols=(120))  # (426, 240)
            V = np.loadtxt("/home/brendan/software/tf2-model-g-velocity/arrays/quiver_array1/u.txt") #, delimiter=" :-) ", usecols=(120))  # (426, 240)

            # swapped U and V around - BJD 2.9.2021
            #U = np.loadtxt("/home/brendan/software/tf2-model-g/arrays/quiver_array37/del_X_dy.txt") #, delimiter=" :-) ", usecols=(120))  # (426, 240)
            #V = np.loadtxt("/home/brendan/software/tf2-model-g/arrays/quiver_array37/del_X_dx.txt") #, delimiter=" :-) ", usecols=(120))  # (426, 240)

            
            # BJD 28.1.2021: u and v are saved as arrays in fluid_model_g.py as fllows:
            # np.savetxt("/home/brendan/software/tf2-model-g/arrays/quiver_array18/u.txt", self.u)
            # np.savetxt("/home/brendan/software/tf2-model-g/arrays/quiver_array18/v.txt", self.v)
            
            N = np.sqrt( U**2 + V**2 )  # there may be a faster numpy "normalize" function
            U1, V1 = U/N, V/N

            #F = 0.001 # normalisation factor
            F = 0.004

            U1 *= F
            V1 *= F
            
            X1, Y1 = np.meshgrid(x1, y1)  # `plot_surface` expects `x` and `y` data to be 2D
            """
#------------------------------------------------------------------

            # velocity fields spearartely for G, X and Y
            # swapped U and V around - BJD 3.9.2021
            U1 = np.loadtxt("/home/brendan/software/tf2-model-g-velocity/arrays/quiver_array1/v_G.txt") # (426, 240)
            V1 = np.loadtxt("/home/brendan/software/tf2-model-g-velocity/arrays/quiver_array1/u_G.txt") # (426, 240)
            
            U2 = np.loadtxt("/home/brendan/software/tf2-model-g-velocity/arrays/quiver_array1/v_X.txt") # (426, 240)
            V2 = np.loadtxt("/home/brendan/software/tf2-model-g-velocity/arrays/quiver_array1/u_X.txt") # (426, 240)
            
            U3 = np.loadtxt("/home/brendan/software/tf2-model-g-velocity/arrays/quiver_array1/v_Y.txt") # (426, 240)
            V3 = np.loadtxt("/home/brendan/software/tf2-model-g-velocity/arrays/quiver_array1/u_Y.txt") # (426, 240)

#---------------normalising arrows--------------------------------
            N1 = np.sqrt( U1**2 + V1**2 )  # there may be a faster numpy "normalize" function
            U1_norm, V1_norm = U1/N1, V1/N1

            #F = 0.001 # normalisation factor
            F = 0.004

            U1_norm *= F
            V1_norm *= F
#-----------------------------------------------
            N2 = np.sqrt( U2**2 + V2**2 )  # there may be a faster numpy "normalize" function
            U2_norm, V2_norm = U2/N2, V2/N2

            #F = 0.001 # normalisation factor
            F = 0.004

            U2_norm *= F
            V2_norm *= F
#-----------------------------------------------
            N3 = np.sqrt( U3**2 + V3**2 )  # there may be a faster numpy "normalize" function
            U3_norm, V3_norm = U3/N3, V3/N3

            #F = 0.001 # normalisation factor
            F = 0.004

            U3_norm *= F
            V3_norm *= F
#-----------------------------------------------

            X1, Y1 = np.meshgrid(x1, y1)  # plot_surface expects x and y data to be 2D

	        # 1st quiver plot for U1 and V1
            fig, hf = plt.subplots(figsize=(10,10))
            hf.set_title("BASE-DENSITY G =1000 'velocity vector' time=" + str(c1))
            Q = hf.quiver(X1[::10, ::10], Y1[::10, ::10], U1_norm[::10, ::10], V1_norm[::10, ::10], units='width',
                pivot='mid', scale=0.1, headwidth=5)#pivot='mid', units='inches')#, scale=1)#, scale=5)
            #Q = hf.quiver(X1[::10, ::10], Y1[::10, ::10], U[::10, ::10], V[::10, ::10], units='width',
                #pivot='mid', scale=0.1, headwidth=7)
            qk = hf.quiverkey(Q, 0.9, 0.9, 5, r'$1 \frac{m}{s}$', labelpos='E',
                   coordinates='figure')
            hf.scatter(X1[::10, ::10], Y1[::10, ::10], color='c', s=0)
            plt.tight_layout()
            plt.savefig('/home/brendan/software/tf2-model-g-velocity/plots/2D_video1/2D_video_velocity_G_1_' + str(c1) + '.png')
            
            # 1st quiver plot for U2 and V2
            fig, hf = plt.subplots(figsize=(10,10))
            hf.set_title("BASE-DENSITY X = 100 'velocity vector' time=" + str(c1))
            Q = hf.quiver(X1[::10, ::10], Y1[::10, ::10], U2_norm[::10, ::10], V2_norm[::10, ::10], units='width',
                pivot='mid', scale=0.1, headwidth=5)#pivot='mid', units='inches')#, scale=1)#, scale=5)
            #Q = hf.quiver(X1[::10, ::10], Y1[::10, ::10], U[::10, ::10], V[::10, ::10], units='width',
                #pivot='mid', scale=0.1, headwidth=7)
            qk = hf.quiverkey(Q, 0.9, 0.9, 5, r'$1 \frac{m}{s}$', labelpos='E',
                   coordinates='figure')
            hf.scatter(X1[::10, ::10], Y1[::10, ::10], color='c', s=0)
            plt.tight_layout()
            plt.savefig('/home/brendan/software/tf2-model-g-velocity/plots/2D_video2/2D_video_velocity_X_2_' + str(c1) + '.png')
            
            # 1st quiver plot for U3 and V3
            fig, hf = plt.subplots(figsize=(10,10))
            hf.set_title("BASE-DENSITY Y = 500 'velocity vector' time=" + str(c1))
            Q = hf.quiver(X1[::10, ::10], Y1[::10, ::10], U3_norm[::10, ::10], V3_norm[::10, ::10], units='width',
                pivot='mid', scale=0.1, headwidth=5)#pivot='mid', units='inches')#, scale=1)#, scale=5)
            #Q = hf.quiver(X1[::10, ::10], Y1[::10, ::10], U[::10, ::10], V[::10, ::10], units='width',
                #pivot='mid', scale=0.1, headwidth=7)
            qk = hf.quiverkey(Q, 0.9, 0.9, 5, r'$1 \frac{m}{s}$', labelpos='E',
                   coordinates='figure')
            hf.scatter(X1[::10, ::10], Y1[::10, ::10], color='c', s=0)
            plt.tight_layout()
            plt.savefig('/home/brendan/software/tf2-model-g-velocity/plots/2D_video3/2D_video_velocity_Y_3_' + str(c1) + '.png')

#----------------------------------------------------------------------            

def charged_nucleation_in_2D(writer, args, R=30, D=25, weights=(0, -10, -8, 8)):
    dx = 2*R / args.height
    x = (np.arange(args.width) - args.width // 2) * dx
    y = (np.arange(args.height) - args.height // 2) * dx
    x, y = np.meshgrid(x, y, indexing='ij')

    def source_G(t):
        amount = np.exp(-0.5*(t-5)**2)
        return (
            np.exp(-0.5*((x-D)**2+y*y)) * weights[0] +
            np.exp(-0.5*((x+D)**2+y*y)) * weights[1]
        ) * amount

    def source_X(t):
        amount = np.exp(-0.5*(t-5)**2)
        return (
            np.exp(-0.5*((x-D)**2+y*y)) * weights[2] +
            np.exp(-0.5*((x+D)**2+y*y)) * weights[3]
        ) * amount

    source_functions = {
        'G': source_G,
        'X': source_X,
    }

    noise_scale = 1e-4
    model_g = ModelG(
        bl_noise(x.shape) * noise_scale,
        bl_noise(x.shape) * noise_scale,
        bl_noise(x.shape) * noise_scale,
        dx,
        dt=args.dt,
        params=args.model_params,
        source_functions=source_functions,
    )

    print("Rendering 'Charged nucleation in 2D'")
    print("Lattice constant dx = {}, time step dt = {}".format(model_g.dx, model_g.dt))
    min_G = -4.672736908320116
    max_G = 0.028719261862332906
    min_X = -3.8935243721220334
    max_X = 1.2854028081816122
    min_Y = -0.7454193158963579
    max_Y = 4.20524950766914
    for n in progressbar.progressbar(range(args.num_frames)):
        model_g.step()
        if n % args.oversampling == 0:
            rgb = [
                6*(-model_g.G + max_G) / (max_G - min_G),
                5*(model_g.Y - min_Y) / (max_Y - min_Y),
                0.7*(model_g.X - min_X) / (max_X - min_X),
            ]
            zero_line = 1 - tf.exp(-600 * model_g.Y**2)
            frame = make_video_frame([c * zero_line for c in rgb])
            writer.append_data(frame)


# TODO: Requires some work. Unstable like this.
def nucleation_3D(writer, args, R=20):
    raise NotImplementedError("Needs some work")
    params = {
        "A": 3.4,
        "B": 13.5,
        "k2": 1.0,
        "k-2": 0.1,
        "k5": 0.9,
        "D_G": 1.0,
        "D_X": 1.0,
        "D_Y": 1.95,
        "density_G": 1.0,
        "density_X": 0.0002,
        "density_Y": 0.043,
        "base-density": 9.0,
        "viscosity": 0.3,
        "speed-of-sound": 1.0,
    }

    dx = 2*R / args.height
    x = (np.arange(args.width) - args.width // 2) * dx
    y = (np.arange(args.height) - args.height // 2) * dx
    z = y
    x, y, z = np.meshgrid(x, y, z, indexing='ij')

    def source_G(t):
        center = np.exp(-0.3*(t-6)**2) * 10
        return -np.exp(-0.5*(x*x+y*y+z*z)) * center

    source_functions = {
        'G': source_G,
    }

    # We need some noise to break spherical symmetry
    noise_scale = 1e-4
    G = bl_noise(x.shape) * noise_scale
    X = bl_noise(x.shape) * noise_scale
    Y = bl_noise(x.shape) * noise_scale
    flow = [
        bl_noise(x.shape) * noise_scale,
        bl_noise(x.shape) * noise_scale,
        bl_noise(x.shape) * noise_scale
    ]

    fluid_model_g = FluidModelG(
        G, X, Y,
        flow,
        dx,
        dt=args.dt,
        params=params,
        source_functions=source_functions,
    )

    flow_particle_origins = []
    for _ in range(1000):
        flow_particle_origins.append([np.random.rand() * s for s in x.shape])

    flow_particles = tf.constant(flow_particle_origins, dtype='float64')
    flow_streaks = 0*x[:,:,0]

    print("Rendering 'Nucleation and Motion in G gradient in 3D'")
    print("Lattice constant dx = {}, time step dt = {}".format(fluid_model_g.dx, fluid_model_g.dt))
    for n in progressbar.progressbar(range(args.num_frames)):
        fluid_model_g.step()
        for _ in range(20):
            indices = tf.cast(flow_particles, 'int32')
            for index in indices.numpy():
                flow_streaks[index[0], index[1]] += 0.15 / args.oversampling
            dx = tf.gather_nd(fluid_model_g.u, indices)
            dy = tf.gather_nd(fluid_model_g.v, indices)
            dz = tf.gather_nd(fluid_model_g.w, indices)
            flow_particles = (flow_particles + tf.stack([dx, dy, dz], axis=1) * 400) % x.shape
        if n % args.oversampling == 0:
            rgb = [
                tf.reduce_mean((7*fluid_model_g.G)**2, axis=2) + flow_streaks,
                tf.reduce_mean((4*fluid_model_g.Y)**2, axis=2),
                tf.reduce_mean((2*fluid_model_g.X)**2, axis=2),
            ]
            frame = make_video_frame(rgb)
            writer.append_data(frame)
            flow_streaks *= 0
            flow_particles = tf.constant(flow_particle_origins, dtype='float64')

if __name__ == '__main__':
    episodes = {
        'nucleation_and_motion_in_fluid_2D': nucleation_and_motion_in_G_gradient_fluid_2D,
        'charged_nucleation_in_2D': charged_nucleation_in_2D,
    }

    parser = argparse.ArgumentParser(description='Render audio samples')
    parser.add_argument('outfile', type=str, help='Output file name')
    parser.add_argument('--params', type=str, help='Parameter YAML file name')
    parser.add_argument('--episode', choices=episodes.keys())
    parser.add_argument('--resolution', choices=RESOLUTIONS.keys(), help='Video and simulation grid resolution')
    parser.add_argument('--width', type=int, help='Video and simulation grid width', metavar='W')
    parser.add_argument('--height', type=int, help='Video and simulation grid height', metavar='H')
    parser.add_argument('--framerate', type=int, help='Video frame rate')
    parser.add_argument('--oversampling', type=int, help='Add extra simulation time steps between video frames for stability')
    parser.add_argument('--video-quality', type=int, help='Video quality factor')
    parser.add_argument('--video-duration', type=float, help='Duration of video to render in seconds')
    parser.add_argument('--simulation-duration', type=float, help='Amount of simulation to run')
    args = parser.parse_args()

    args.model_params = {}
    if args.params:
        with open(args.params) as f:
            params = yaml.load(f, Loader=Loader)
            for key, value in params.items():
                if not getattr(args, key):
                    setattr(args, key, value)

    if not args.episode:
        raise ValueError("Missing episode argument. Must be present in either parameter YAML file or as a program argument.")

    if not args.framerate:
        args.framerate = 24
    if not args.oversampling:
        args.oversampling = 1
    if not args.video_quality:
        args.video_quality = 10

    writer = imageio.get_writer(args.outfile, fps=args.framerate, quality=args.video_quality, macro_block_size=1)

    # Compute derived parameters
    if args.resolution:
        width, height = RESOLUTIONS[args.resolution]
        if not args.width:
            args.width = width
        if not args.height:
            args.height = height
    if (not args.width) or (not args.height):
        raise ValueError("Invalid or missing resolution")
    args.aspect = args.width / args.height
    args.num_frames = int(args.video_duration * args.oversampling * args.framerate)
    args.dt = args.simulation_duration / args.num_frames

    episodes[args.episode](writer, args)
    writer.close()
#------------------------------------------------------------------------------
def save1():
    os.system("ffmpeg -r 1 -i /home/brendan/software/tf2-model-g-velocity/plots/2D_video1/2D_video_velocity_G_1_%01d.png -vcodec mpeg4 -y nucleation_and_motion_in_fluid_2D_______BASE_DENSITY_G_=1000_X_=100_Y_=500_____velocity_vector_G___2d____video_____4.mp4")
    os.system("ffmpeg -r 1 -i /home/brendan/software/tf2-model-g-velocity/plots/2D_video2/2D_video_velocity_X_2_%01d.png -vcodec mpeg4 -y nucleation_and_motion_in_fluid_2D_______BASE_DENSITY_G_=1000_X_=100_Y_=500_____velocity_vector_X___2d____video_____4.mp4")
    os.system("ffmpeg -r 1 -i /home/brendan/software/tf2-model-g-velocity/plots/2D_video3/2D_video_velocity_Y_3_%01d.png -vcodec mpeg4 -y nucleation_and_motion_in_fluid_2D_______BASE_DENSITY_G_=1000_X_=100_Y_=500_____velocity_vector_Y___2d____video_____4.mp4")


    #ffmpeg -i /home/brendan/video/nucleation_and_motion_in_fluid_2D_______BASE_DENSITY_G_=${BASE_DENSITY1[i]}_X_=${BASE_DENSITY2[i]}_Y_=${BASE_DENSITY3[i]}_batch_5_____velocity_vector_G___2d____video_____8.mp4 -f yuv4mpegpipe - | yuvfps -s 30:1 -r 30:1 | ffmpeg -f yuv4mpegpipe -i  - -b 28800k /home/brendan/video/nucleation_and_motion_in_fluid_2D_______BASE_DENSITY_G_=${BASE_DENSITY1[i]}_X_=${BASE_DENSITY2[i]}_Y_=${BASE_DENSITY3[i]}_batch_5_____velocity_vector_G___2d____video_____8___speededUp30FramesPerSec.mp4

    #ffmpeg -i /home/brendan/video/nucleation_and_motion_in_fluid_2D_______BASE_DENSITY_G_=${BASE_DENSITY1[i]}_X_=${BASE_DENSITY2[i]}_Y_=${BASE_DENSITY3[i]}_batch_5_____velocity_vector_X___2d____video_____8.mp4 -f yuv4mpegpipe - | yuvfps -s 30:1 -r 30:1 | ffmpeg -f yuv4mpegpipe -i  - -b 28800k /home/brendan/video/nucleation_and_motion_in_fluid_2D_______BASE_DENSITY_G_=${BASE_DENSITY1[i]}_X_=${BASE_DENSITY2[i]}_Y_=${BASE_DENSITY3[i]}_batch_5_____velocity_vector_X___2d____video_____8___speededUp30FramesPerSec.mp4

    #ffmpeg -i /home/brendan/video/nucleation_and_motion_in_fluid_2D_______BASE_DENSITY_G_=${BASE_DENSITY1[i]}_X_=${BASE_DENSITY2[i]}_Y_=${BASE_DENSITY3[i]}_batch_5_____velocity_vector_Y___2d____video_____8.mp4 -f yuv4mpegpipe - | yuvfps -s 30:1 -r 30:1 | ffmpeg -f yuv4mpegpipe -i  - -b 28800k /home/brendan/video/nucleation_and_motion_in_fluid_2D_______BASE_DENSITY_G_=${BASE_DENSITY1[i]}_X_=${BASE_DENSITY2[i]}_Y_=${BASE_DENSITY3[i]}_batch_5_____velocity_vector_Y___2d____video_____8___speededUp30FramesPerSec.mp4

save1()