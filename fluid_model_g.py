import warnings
import tensorflow as tf
import numpy as np
import util
import io # BJD added 18.11.2020
from pde_solver import PDESolverDx
from integrators.model_g import polynomial_order_4_centered as reaction_integrator
from integrators.model_g import steady_state
#from render_video import c1

#c1 = 0

# BJD note test - velocity_fields_1 new branch 23 June 2021

DEFAULT_PARAMS = {
    "A": 3.42,
    "B": 14.5,
    "k2": 1.0,
    "k-2": 0.1,
    "k5": 0.9,
    "D_G": 1.0,
    "D_X": 1.0,
    "D_Y": 2.0,
    "density_G": 2.0,
    "density_X": 1.0,
    "density_Y": 1.5,
    "base-density": 6.0,
    "viscosity": 0.1,
    "speed-of-sound": 0.2,
}


class FluidModelG(PDESolverDx):
    """
    Model G on a fluid medium
    """
    # BJD concentration_vel_G_x 28.1.2021
    #def __init__(self, concentration_G, concentration_X, concentration_Y, concentration_vel_G_x, u, dx, dt=None, params=None, source_functions=None):
    def __init__(self, concentration_G, concentration_X, concentration_Y, u, dx, dt=None, params=None, source_functions=None):
        if dt is None:
            dt = 0.1 * dx

        if dt > 0.5 * dx:
            warnings.warn("Time increment {} too large for simulation stability with grid constant {}".format(dt, dx))

        #super().__init__(dx, dt, concentration_G.shape) # BJD original 13.6.2021
        super().__init__(dx, dt, concentration_G.shape, concentration_X.shape, concentration_Y.shape) # BJD change 13.6.2021
        self.params = params or DEFAULT_PARAMS
        self.source_functions = source_functions or {}

        self.G = tf.constant(concentration_G, 'float64')
        self.X = tf.constant(concentration_X, 'float64')
        self.Y = tf.constant(concentration_Y, 'float64')
        #self.vel_G_x = tf.constant(concentration_vel_G_x, 'float64')   # BJD 28.1.2021

        G0, X0, Y0 = steady_state(self.params['A'], self.params['B'], self.params['k2'], self.params['k-2'], self.params['k5'])

        if len(u) != self.dims:
            raise ValueError("{0}-dimensional flow must have {0} components".format(self.dims))

        c2 = self.params["speed-of-sound"]**2
        viscosity = self.params["viscosity"]
        if self.dims == 1:
            raise ValueError("1D not supported")
        elif self.dims == 2:
            #self.u = tf.constant(u[0], 'float64') # original 2 lines
            #self.v = tf.constant(u[1], 'float64')

            #BJD adaptions - 6 lines below 9.6.2021 
            self.u_X = tf.constant(u[0], 'float64')
            self.v_X = tf.constant(u[1], 'float64')
            self.u_Y = tf.constant(u[2], 'float64')
            self.v_Y = tf.constant(u[3], 'float64')
            self.u_G = tf.constant(u[4], 'float64')
            self.v_G = tf.constant(u[5], 'float64')
                        
            omega_x, omega_y = self.omega_x, self.omega_y
            omega2 = omega_x**2 + omega_y**2
            omega2_x = tf.constant(omega2 + 1/3 * omega_x * (omega_x + omega_y), "complex128")
            omega2_y = tf.constant(omega2 + 1/3 * omega_y * (omega_x + omega_y), "complex128")
            decay_x = tf.exp(-viscosity * omega2_x * self.dt)
            decay_y = tf.exp(-viscosity * omega2_y * self.dt)

            delta = tf.constant(-omega2 * self.dt, "complex128")
            decay_G = tf.exp(self.params['D_G'] * delta)
            decay_X = tf.exp(self.params['D_X'] * delta)
            decay_Y = tf.exp(self.params['D_Y'] * delta)

            def flow_integrator(rho, u, v):
                """
                Flow is integrated with respect to the total log density (rho)
                """
                # Enter Fourier Domain
                f_rho = self.fft(tf.cast(rho, 'complex128'))
                waves_x = self.fft(tf.cast(u, 'complex128'))
                waves_y = self.fft(tf.cast(v, 'complex128'))

                # Viscosity and internal shear
                waves_x *= decay_x
                waves_y *= decay_y

                # Exit Fourier Domain
                u = tf.cast(self.ifft(waves_x), 'float64')
                v = tf.cast(self.ifft(waves_y), 'float64')

                # Calculate gradients
                rho_dx = tf.cast(self.ifft(f_rho * self.kernel_dx), 'float64')
                rho_dy = tf.cast(self.ifft(f_rho * self.kernel_dy), 'float64')
                u_dx = tf.cast(self.ifft(waves_x * self.kernel_dx), 'float64')
                u_dy = tf.cast(self.ifft(waves_x * self.kernel_dy), 'float64')
                v_dx = tf.cast(self.ifft(waves_y * self.kernel_dx), 'float64')
                v_dy = tf.cast(self.ifft(waves_y * self.kernel_dy), 'float64')
                divergence = u_dx + v_dy

                # This would handle log density continuity but it's actually handled individually for G, X and Y
                # rho -= (u*rho_dx + v*rho_dy + divergence) * self.dt

                # Self-advect flow
                du = -u*u_dx - v*u_dy
                dv = -u*v_dx - v*v_dy

                # Propagate pressure waves
                du -= c2 * rho_dx
                dv -= c2 * rho_dy

                # Apply strain
                du += viscosity * (rho_dx * (u_dx + u_dx) + rho_dy * (u_dy + v_dx) - 2/3*rho_dx * divergence)
                dv += viscosity * (rho_dx * (v_dx + u_dy) + rho_dy * (v_dy + v_dy) - 2/3*rho_dy * divergence)

                u += du * self.dt
                v += dv * self.dt

                return u, v, divergence

            #def diffusion_advection_integrator(G, X, Y, vel_G_x, u, v, divergence):
            #def diffusion_advection_integrator(G, X, Y, u, v, divergence): # BJD original 10.6.2021
            def diffusion_advection_integrator(G, X, Y, u_X, v_X, u_Y, v_Y, u_G, v_G, divergence1,divergence2, divergence3): # BJD original 10.6.2021
            
                f_G = self.fft(tf.cast(G, 'complex128'))
                f_X = self.fft(tf.cast(X, 'complex128'))
                f_Y = self.fft(tf.cast(Y, 'complex128'))

                f_G *= decay_G
                f_X *= decay_X
                f_Y *= decay_Y

                G = tf.cast(self.ifft(f_G), 'float64')
                X = tf.cast(self.ifft(f_X), 'float64')
                Y = tf.cast(self.ifft(f_Y), 'float64')

                G_dx = tf.cast(self.ifft(f_G * self.kernel_dx), 'float64')
                G_dy = tf.cast(self.ifft(f_G * self.kernel_dy), 'float64')
                X_dx = tf.cast(self.ifft(f_X * self.kernel_dx), 'float64')
                X_dy = tf.cast(self.ifft(f_X * self.kernel_dy), 'float64')
                Y_dx = tf.cast(self.ifft(f_Y * self.kernel_dx), 'float64')
                Y_dy = tf.cast(self.ifft(f_Y * self.kernel_dy), 'float64')

                #G -= (u*G_dx + v*G_dy + G*divergence) * self.dt # BJD original
                G -= (u_G*G_dx + v_G*G_dy + G*divergence1) * self.dt # BJD change 10.6.2021
                #X -= (u*X_dx + v*X_dy + X*divergence) * self.dt # BJD original
                #Y -= (u*Y_dx + v*Y_dy + Y*divergence) * self.dt # BJD original
                X -= (u_X*X_dx + v_X*X_dy + X*divergence2) * self.dt # BJD change 10.6.2021
                Y -= (u_Y*Y_dx + v_Y*Y_dy + Y*divergence3) * self.dt # BJD change 10.6.2021

                #vel_G_x = tf.cast(u*G_dx, 'float64')
                #vel_G_x -= u*G_dx
                #print("Value of u*G_dx: ", u*G_dx)
                #np.savetxt("/home/brendan/software/tf2-model-g/arrays/quiver_array13/G.txt", vel_G_x)   
                return G, X, Y     #, vel_G_x #, u*G_dx #, G_velocity_field_x
                
        elif self.dims == 3:
            self.u = tf.constant(u[0], 'float64')
            self.v = tf.constant(u[1], 'float64')
            self.w = tf.constant(u[2], 'float64')

            omega_x, omega_y, omega_z = self.omega_x, self.omega_y, self.omega_z
            omega2 = omega_x**2 + omega_y**2 + omega_z**2
            omega2_x = tf.constant(omega2 + 1/3 * omega_x * (omega_x + omega_y + omega_z), "complex128")
            omega2_y = tf.constant(omega2 + 1/3 * omega_y * (omega_x + omega_y + omega_z), "complex128")
            omega2_z = tf.constant(omega2 + 1/3 * omega_z * (omega_x + omega_y + omega_z), "complex128")
            decay_x = tf.exp(-viscosity * omega2_x * self.dt)
            decay_y = tf.exp(-viscosity * omega2_y * self.dt)
            decay_z = tf.exp(-viscosity * omega2_z * self.dt)

            delta = tf.constant(-omega2 * self.dt, "complex128")
            decay_G = tf.exp(self.params['D_G'] * delta)
            decay_X = tf.exp(self.params['D_X'] * delta)
            decay_Y = tf.exp(self.params['D_Y'] * delta)

            def flow_integrator(rho, u, v, w):
                # Enter Fourier Domain
                f_rho = self.fft(tf.cast(rho, 'complex128'))
                waves_x = self.fft(tf.cast(u, 'complex128'))
                waves_y = self.fft(tf.cast(v, 'complex128'))
                waves_z = self.fft(tf.cast(w, 'complex128'))

                # Viscosity and internal shear
                waves_x *= decay_x
                waves_y *= decay_y
                waves_z *= decay_z

                # Exit Fourier Domain
                u = tf.cast(self.ifft(waves_x), 'float64')
                v = tf.cast(self.ifft(waves_y), 'float64')
                w = tf.cast(self.ifft(waves_z), 'float64')

                # Calculate gradients
                rho_dx = tf.cast(self.ifft(f_rho * self.kernel_dx), 'float64')
                rho_dy = tf.cast(self.ifft(f_rho * self.kernel_dy), 'float64')
                rho_dz = tf.cast(self.ifft(f_rho * self.kernel_dz), 'float64')

                u_dx = tf.cast(self.ifft(waves_x * self.kernel_dx), 'float64')
                u_dy = tf.cast(self.ifft(waves_x * self.kernel_dy), 'float64')
                u_dz = tf.cast(self.ifft(waves_x * self.kernel_dz), 'float64')

                v_dx = tf.cast(self.ifft(waves_y * self.kernel_dx), 'float64')
                v_dy = tf.cast(self.ifft(waves_y * self.kernel_dy), 'float64')
                v_dz = tf.cast(self.ifft(waves_y * self.kernel_dz), 'float64')

                w_dx = tf.cast(self.ifft(waves_z * self.kernel_dx), 'float64')
                w_dy = tf.cast(self.ifft(waves_z * self.kernel_dy), 'float64')
                w_dz = tf.cast(self.ifft(waves_z * self.kernel_dz), 'float64')

                divergence = u_dx + v_dy + w_dz

                # This would handle log density continuity, but we do G, X and Y individually
                # rho -= (u*rho_dx + v*rho_dy + w*rho_dz + divergence) * self.dt

                # Self-advect flow
                du = -u*u_dx - v*u_dy - w*u_dz
                dv = -u*v_dx - v*v_dy - w*v_dz
                dw = -u*w_dx - v*w_dy - w*w_dz

                # Propagate pressure waves
                du -= c2 * rho_dx
                dv -= c2 * rho_dy
                dw -= c2 * rho_dz

                # Apply strain
                du += viscosity * (rho_dx * (u_dx + u_dx) + rho_dy * (u_dy + v_dx) + rho_dz * (u_dz + w_dx) - 2/3*rho_dx * divergence)
                dv += viscosity * (rho_dx * (v_dx + u_dy) + rho_dy * (v_dy + v_dy) + rho_dz * (v_dz + w_dy) - 2/3*rho_dy * divergence)
                dw += viscosity * (rho_dx * (w_dx + u_dz) + rho_dy * (w_dy + v_dz) + rho_dz * (w_dz + w_dz) - 2/3*rho_dz * divergence)

                u += du * self.dt
                v += dv * self.dt
                w += dw * self.dt

                return u, v, w, divergence
            def diffusion_advection_integrator(G, X, Y, u, v, w, divergence):
                f_G = self.fft(tf.cast(G, 'complex128'))
                f_X = self.fft(tf.cast(X, 'complex128'))
                f_Y = self.fft(tf.cast(Y, 'complex128'))

                f_G *= decay_G
                f_X *= decay_X
                f_Y *= decay_Y

                G = tf.cast(self.ifft(f_G), 'float64')
                X = tf.cast(self.ifft(f_X), 'float64')
                Y = tf.cast(self.ifft(f_Y), 'float64')

                G_dx = tf.cast(self.ifft(f_G * self.kernel_dx), 'float64')
                G_dy = tf.cast(self.ifft(f_G * self.kernel_dy), 'float64')
                G_dz = tf.cast(self.ifft(f_G * self.kernel_dz), 'float64')
                X_dx = tf.cast(self.ifft(f_X * self.kernel_dx), 'float64')
                X_dy = tf.cast(self.ifft(f_X * self.kernel_dy), 'float64')
                X_dz = tf.cast(self.ifft(f_X * self.kernel_dz), 'float64')
                Y_dx = tf.cast(self.ifft(f_Y * self.kernel_dx), 'float64')
                Y_dy = tf.cast(self.ifft(f_Y * self.kernel_dy), 'float64')
                Y_dz = tf.cast(self.ifft(f_Y * self.kernel_dz), 'float64')

                G -= (u*G_dx + v*G_dy + w*G_dz + (G+G0)*divergence) * self.dt
                X -= (u*X_dx + v*X_dy + w*X_dz + (X+X0)*divergence) * self.dt
                Y -= (u*Y_dx + v*Y_dy + w*Y_dz + (Y+Y0)*divergence) * self.dt

                return G, X, Y
        else:
            raise ValueError('Only up to 3D supported')

        reaction_integrator_curried = lambda con_G, con_X, con_Y: reaction_integrator(
            con_G, con_X, con_Y,
            self.dt, self.params['A'], self.params['B'], self.params['k2'], self.params['k-2'], self.params['k5']
        )

        self.reaction_integrator = tf.function(reaction_integrator_curried)
        self.flow_integrator = tf.function(flow_integrator)
        self.diffusion_advection_integrator = tf.function(diffusion_advection_integrator)

    def step(self):
        self.G, self.X, self.Y = self.reaction_integrator(self.G, self.X, self.Y)
        density_of_reactants = (
            self.params['density_G'] * self.G +
            self.params['density_X'] * self.X +
            self.params['density_Y'] * self.Y
        )
        # rho = tf.math.log(self.params['base-density'] + density_of_reactants) # BJD original here
        rho1 = tf.math.log(self.params['base-density1'] + density_of_reactants) # BJD added 10.6.2021
        rho2 = tf.math.log(self.params['base-density2'] + density_of_reactants) # BJD added 10.6.2021
        rho3 = tf.math.log(self.params['base-density3'] + density_of_reactants) # BJD added 10.6.2021

        if self.dims == 2:
            #c1 = c1 + 1 # BJD added 18.11.2020
            #u, v = self.u, self.v  # Store unintegrated flow so that we're on the same timestep --- BJD original line 9.6.2021
            u_X, v_X = self.u_X, self.v_X  # Store unintegrated flow so that we're on the same timestep --- BJD added 9.6.2021
            u_Y, v_Y = self.u_Y, self.v_Y  # Store unintegrated flow so that we're on the same timestep --- BJD added 9.6.2021
            u_G, v_G = self.u_G, self.v_G  # Store unintegrated flow so that we're on the same timestep --- BJD added 9.6.2021

            #self.u, self.v, divergence = self.flow_integrator(rho, self.u, self.v) -BJD original line 9.6.2021
            self.u_X, self.v_X, divergence1 = self.flow_integrator(rho1, self.u_X, self.v_X) #--- BJD added 9.6.2021
            self.u_Y, self.v_Y, divergence2 = self.flow_integrator(rho2, self.u_Y, self.v_Y) #--- BJD added 9.6.2021
            self.u_G, self.v_G, divergence3 = self.flow_integrator(rho3, self.u_G, self.v_G) #--- BJD added 9.6.2021

            #BJD altered line below ----- G_velocity_field_x
            #self.G, self.X, self.Y, self.u*G_dx = self.diffusion_advection_integrator(self.G, self.X, self.Y, u, v, divergence)
            #self.G, self.X, self.Y, self.vel_G_x = self.diffusion_advection_integrator(self.G, self.X, self.Y, self.vel_G_x, u, v, divergence)
            #self.G, self.X, self.Y = self.diffusion_advection_integrator(self.G, self.X, self.Y, u, v, divergence) # BJD original line 10.6.2021
            self.G, self.X, self.Y = self.diffusion_advection_integrator(self.G, self.X, self.Y, u_X, v_X, u_Y, v_Y, u_G, v_G, divergence1, divergence2, divergence3) #--- BJD added 10.6.2021
            print(" Value of X: ", self.X) # ***** BJD inserted this line 13.11.2020 *****
            #print("Value of u: ", self.u) # ***** BJD inserted this line 28.1.2021 *****
# =======================BJD 18.11.2020================================================      

            # this below line worked!! BJD
            #np.savetxt("/home/brendan/software/tf2-model-g/arrays/array28/X.txt", self.X) # https://www.python-course.eu/numpy_reading_writing.php
            #np.savetxt("/home/brendan/software/tf2-model-g/arrays/array28/Y.txt", self.Y)
            #np.savetxt("/home/brendan/software/tf2-model-g/arrays/array28/G.txt", self.G)

            #np.savetxt("/home/brendan/software/tf2-model-g/arrays/quiver_array13/G.txt", u*G_dx)

            #print("Value of u*G_dx: ", self.G_velocity_field_x)
            #np.savetxt("/home/brendan/software/tf2-model-g/arrays/quiver_array30/u.txt", self.u) # BJD 1.2.2021
            #np.savetxt("/home/brendan/software/tf2-model-g/arrays/quiver_array30/v.txt", self.v) # BJD 1.2.2021

# ========================================================================================     
        elif self.dims == 3:
            u, v, w = self.u, self.v, self.w  # Store unintegrated flow so that we're on the same timestep
            self.u, self.v, self.w, divergence = self.flow_integrator(rho, self.u, self.v, self.w)
            self.G, self.X, self.Y = self.diffusion_advection_integrator(self.G, self.X, self.Y, u, v, w, divergence)
            print(" Value of u: ", self.u) # ***** BJD inserted this line 17.1.2021 *****
# =======================BJD 22.4.2021================================================      

            #np.savetxt("/home/brendan/software/tf2-model-g/arrays/quiver3D_array31/u.txt", self.u) # BJD 22.4.2021
            #np.savetxt("/home/brendan/software/tf2-model-g/arrays/quiver3D_array31/v.txt", self.v) # BJD 22.4.2021
            #np.savetxt("/home/brendan/software/tf2-model-g/arrays/quiver3D_array31/w.txt", self.w) # BJD 22.4.2021
# ========================================================================================    

        zero = lambda t: 0
        source_G = self.source_functions.get('G', zero)(self.t)
        source_X = self.source_functions.get('X', zero)(self.t)
        source_Y = self.source_functions.get('Y', zero)(self.t)
        self.G += self.dt * source_G
        self.X += self.dt * source_X
        self.Y += self.dt * source_Y
        self.t += self.dt
    
        #np.savetxt("file_" + str(c1) + ".txt", self.X)
        #with io.open("file_" + str(c1) + ".txt", 'w', encoding='utf-8') as f:
            #f.write(str(func(c1))
        #if c1 == 10:
        #    c1 = 0
        

    def numpy(self):
        if self.dims == 2:
            u = (self.u.numpy(), self.v.numpy())
        elif self.dims == 3:
            u = (self.u.numpy(), self.v.numpy(), self.w.numpy())
        return self.G.numpy(), self.X.numpy(), self.Y.numpy(), u
