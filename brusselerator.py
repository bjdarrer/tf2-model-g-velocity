import tensorflow as tf
import numpy as np
from integrators.brusselerator import polynomial_order_4_centered as reaction_integrator

DEFAULT_PARAMS = {
    "A": 1.0,
    "B": 2.0,
    "k4": 1.0,
    "Dy": 8.0,
}


class Brusselerator(object):
    """
    Brusselerator is a simpler version of Model G that is either globally critical or sub-critical.

    Used as a sanity check to make sure that Model G produces the same behaviour when the G concentration is held constant
    """

    def __init__(self, concentration_X, concentration_Y, dx, params=None, fixed_point_iterations=3, source_functions=None):
        if concentration_X.shape != concentration_Y.shape:
            raise ValueError("Concentration shapes must match")
        self.dx = dx
        self.dt = dx*0.1
        self.t = 0

        self.concentration_X = tf.constant(concentration_X, dtype="float64")
        self.concentration_Y = tf.constant(concentration_Y, dtype="float64")
        self.params = params or DEFAULT_PARAMS
        self.fixed_point_iterations = fixed_point_iterations
        self.source_functions = source_functions or {}

        l = concentration_X.shape[-1]
        if any(s != l for s in concentration_X.shape):
            raise ValueError('Only square grids supported')

        ratio = 2*np.pi / (l*self.dx)
        delta = self.dt * ratio**2
        omega2 = (l//2 - tf.abs(tf.range(l) - l//2))**2
        dims = len(concentration_X.shape)
        if dims == 1:
            decay_x = tf.exp(-delta * tf.cast(omega2, 'complex128'))
            decay_y = tf.exp(-self.params['Dy'] * delta * tf.cast(omega2, 'complex128'))
            def diffusion_integrator(con_X, con_Y):
                f = tf.signal.fft(tf.cast(con_X, 'complex128'))
                f *= decay_x
                con_X = tf.cast(tf.math.real(tf.signal.ifft(f)), 'float64')

                f = tf.signal.fft(tf.cast(con_Y, 'complex128'))
                f *= decay_y
                con_Y = tf.cast(tf.math.real(tf.signal.ifft(f)), 'float64')

                return con_X, con_Y
        elif dims == 2:
            omega2_x, omega2_y = tf.meshgrid(omega2, omega2)
            decay_x = tf.exp(-delta * tf.cast(omega2_x + omega2_y, 'complex128'))
            decay_y = tf.exp(-self.params['Dy'] * delta * tf.cast(omega2_x + omega2_y, 'complex128'))
            def diffusion_integrator(con_X, con_Y):
                f = tf.signal.fft2d(tf.cast(con_X, 'complex128'))
                f *= decay_x
                con_X = tf.cast(tf.math.real(tf.signal.ifft2d(f)), 'float64')

                f = tf.signal.fft2d(tf.cast(con_Y, 'complex128'))
                f *= decay_y
                con_Y = tf.cast(tf.math.real(tf.signal.ifft2d(f)), 'float64')

                return con_X, con_Y
        elif dims == 3:
            omega2_x, omega2_y, omega2_z = tf.meshgrid(omega2, omega2, omega2)
            decay_x = tf.exp(-delta * tf.cast(omega2_x + omega2_y + omega2_z, 'complex128'))
            decay_y = tf.exp(-self.params['Dy'] * delta * tf.cast(omega2_x + omega2_y + omega2_z, 'complex128'))
            def diffusion_integrator(con_X, con_Y):
                f = tf.signal.fft3d(tf.cast(con_X, 'complex128'))
                f *= decay_x
                con_X = tf.cast(tf.math.real(tf.signal.ifft3d(f)), 'float64')

                f = tf.signal.fft3d(tf.cast(con_Y, 'complex128'))
                f *= decay_y
                con_Y = tf.cast(tf.math.real(tf.signal.ifft3d(f)), 'float64')

                return con_X, con_Y
        else:
            raise ValueError('Only up to 3D supported')

        reaction_integrator_curried = lambda con_X, con_Y: reaction_integrator(con_X, con_Y, self.dt, self.params['A'], self.params['B'], self.params['k4'])

        self.diffusion_integrator = tf.function(diffusion_integrator)
        self.reaction_integrator = tf.function(reaction_integrator_curried)

    def step(self):
        self.concentration_X, self.concentration_Y = self.diffusion_integrator(self.concentration_X, self.concentration_Y)
        self.concentration_X, self.concentration_Y = self.reaction_integrator(self.concentration_X, self.concentration_Y)
        zero = lambda t: 0
        source_X = self.source_functions.get('X', zero)(self.t)
        source_Y = self.source_functions.get('Y', zero)(self.t)
        self.concentration_X += self.dt * source_X
        self.concentration_Y += self.dt * source_Y
        self.t += self.dt

    def numpy(self):
        return self.concentration_X.numpy(), self.concentration_Y.numpy()


if __name__ == '__main__':
    from util import bl_noise
    import pylab
    from matplotlib.animation import FuncAnimation

    x = np.linspace(-5, 5, 128)
    dx = x[1] - x[0]
    x, y = np.meshgrid(x, x)

    r2 = x*x+y*y
    source_X = lambda t: np.exp(-(x-4)**2-y*y) / (t + 1)
    zero = lambda t: 0
    source_functions = {
        'X': source_X,
        'Y': zero,
    }
    brusselerator = Brusselerator(np.exp(-0.2*r2)*bl_noise(x.shape), np.exp(-0.3*r2), dx, source_functions=source_functions)
    X, Y = brusselerator.numpy()
    plots = []
    plots.extend(pylab.plot(x[0], X[64]))
    plots.extend(pylab.plot(x[0], Y[64]))
    pylab.ylim(-1.5, 1.5)

    def update(frame):
        brusselerator.step()
        X, Y = brusselerator.numpy()
        plots[0].set_ydata(X[64])
        plots[-1].set_ydata(Y[64])
        return plots

    FuncAnimation(pylab.gcf(), update, frames=range(2000), init_func=lambda: plots, blit=True, repeat=False, interval=10)
    pylab.show()

    X, Y = brusselerator.numpy()
    pylab.imshow(X)
    pylab.show()
