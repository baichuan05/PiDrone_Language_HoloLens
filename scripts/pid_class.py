#!/usr/bin/env python
from __future__ import division
import rospy


#####################################################
#						PID							#
#####################################################
class PIDaxis():
    def __init__(self, kp, ki, kd, kp_upper=None, i_range=None, d_range=None, control_range=(1000, 2000), midpoint=1500):
        # Tuning
        self.kp = kp
        self.ki = ki
        self.kd = kd
        # Config
        self.kp_upper = kp_upper
        self.i_range = i_range
        self.d_range = d_range
        self.control_range = control_range
        self.midpoint = midpoint
        self.smoothing = True
        # Internal
        self._old_err = None
        self._p = 0
        self._i = 0
        self._d = 0
        self._dd = 0
        self._ddd = 0

    def step(self, err, time_elapsed, error=None):

        if self._old_err is None:
            # First time around prevent d term spike
            self._old_err = err

        # Find the p component
        if self.kp_upper is not None and err < 0:
            self._p = err * self.kp_upper
        else: 
            self._p = err * self.kp

        # Find the i component
        self._i += err * self.ki * time_elapsed
        if self.i_range is not None:
            self._i = max(self.i_range[0], min(self._i, self.i_range[1]))

        # Find the d component
        self._d = (err - self._old_err) * self.kd / time_elapsed
        if self.d_range is not None:
            self._d = max(self.d_range[0], min(self._d, self.d_range[1]))
        self._old_err = err
 
        # Smooth over the last three d terms
        if self.smoothing:
            self._d = (self._d * 8.0 + self._dd * 5.0 + self._ddd * 2.0)/15.0
            self._ddd = self._dd
            self._dd = self._d

        # Update p, i, d fields for the error message
        if error is not None:
            error.p = self._p
            error.i = self._i
            error.d = self._d

        # Calculate control output
        raw_output = self._p + self._i + self._d
        output = min(max(raw_output + self.midpoint, self.control_range[0]), self.control_range[1])

        return output


class PID:

    height_factor = 1.238   
    battery_factor = 0.75

    def __init__(self,

                 roll=PIDaxis(4., 4.0, 0.0, control_range=(1400, 1600), midpoint=1500),
                 roll_low=PIDaxis(4., 0.2, 0.0, control_range=(1400, 1600), midpoint=1500),

                 pitch=PIDaxis(4., 4.0, 0.0, control_range=(1400, 1600), midpoint=1500),
                 pitch_low=PIDaxis(4., 0.2, 0.0, control_range=(1400, 1600), midpoint=1500),

                 yaw=PIDaxis(0.0, 0.0, 0.0),

                 # Kv 2300 motors have midpoint 1300, Kv 2550 motors have midpoint 1250
                 throttle=PIDaxis(1.0/height_factor * battery_factor, 0.5/height_factor * battery_factor,
                                  2.0/height_factor * battery_factor, kp_upper=1.0/height_factor * battery_factor,
                                  i_range=(-400, 400), control_range=(1200, 2000), d_range=(-40, 40), midpoint=1250),
                 throttle_low=PIDaxis(1.0/height_factor * battery_factor, 0.05/height_factor * battery_factor,
                                      2.0/height_factor * battery_factor, kp_upper=1.0/height_factor * battery_factor,
                                      i_range=(0, 400), control_range=(1200, 2000), d_range=(-40, 40), midpoint=1250)
                 ):

        self.trim_controller_cap_plane = 5.0
        self.trim_controller_thresh_plane = 0.01

        self.roll = roll
        self.roll_low = roll_low

        self.pitch = pitch
        self.pitch_low = pitch_low

        self.yaw = yaw

        self.trim_controller_cap_throttle = 5.0
        self.trim_controller_thresh_throttle = 5.0

        self.throttle = throttle
        self.throttle_low = throttle_low

        self.sp = None
        self._t = None

        # Steve005 presets
        self.roll_low._i = 15 
        self.pitch_low._i = 8 

        self.throttle_low.init_i = 130
        self.throttle.init_i = 0.0
        self.throttle.mw_angle_alt_scale = 1.0
        self.reset()

    def reset(self, state_controller=None):
        self._t = None
        self.throttle_low._i = self.throttle_low.init_i
        self.throttle._i = self.throttle.init_i

        if state_controller is not None:
            state_controller.set_z = state_controller.initial_set_z

    def step(self, error, cmd_yaw_velocity=0):
        # First time around prevent time spike
        if self._t is None:
            time_elapsed = 1
        else:
            time_elapsed = rospy.get_time() - self._t

        self._t = rospy.get_time()

        # Compute roll command
        if abs(error.x.err) < self.trim_controller_thresh_plane:
            cmd_r = self.roll_low.step(error.x.err, time_elapsed, error.x)
            self.roll._i = 0
        else:
            if error.x.err > self.trim_controller_cap_plane:
                self.roll_low.step(self.trim_controller_cap_plane, time_elapsed, error.x)
            elif error.x.err < -self.trim_controller_cap_plane:
                self.roll_low.step(-self.trim_controller_cap_plane, time_elapsed, error.x)
            else:
                self.roll_low.step(error.x.err, time_elapsed, error.x)

            cmd_r = self.roll_low._i + self.roll.step(error.x.err, time_elapsed, error.x)

        # Compute pitch command
        if abs(error.y.err) < self.trim_controller_thresh_plane:
            cmd_p = self.pitch_low.step(error.y.err, time_elapsed, error.y)
            self.pitch._i = 0
        else:
            if error.y.err > self.trim_controller_cap_plane:
                self.pitch_low.step(self.trim_controller_cap_plane, time_elapsed, error.y)
            elif error.y.err < -self.trim_controller_cap_plane:
                self.pitch_low.step(-self.trim_controller_cap_plane, time_elapsed, error.y)
            else:
                self.pitch_low.step(error.y.err, time_elapsed, error.y)

            cmd_p = self.pitch_low._i + self.pitch.step(error.y.err, time_elapsed, error.y)

        # Compute yaw command
        cmd_y = 1500 + cmd_yaw_velocity

        # Compute throttle command
        if abs(error.z.err) < self.trim_controller_thresh_throttle:
            cmd_t = self.throttle_low.step(error.z.err, time_elapsed, error.z)
            self.throttle_low._i += self.throttle._i
            self.throttle._i = 0
        else:
            if error.z.err > self.trim_controller_cap_throttle:
                self.throttle_low.step(self.trim_controller_cap_throttle, time_elapsed, error.z)
            elif error.z.err < -self.trim_controller_cap_throttle:
                self.throttle_low.step(-self.trim_controller_cap_throttle, time_elapsed, error.z)
            else:
                self.throttle_low.step(error.z.err, time_elapsed, error.z)

            cmd_t = self.throttle_low._i + self.throttle.step(error.z.err, time_elapsed, error.z)

            # jgo: this seems to mostly make a difference before the I term has
            # built enough to be stable, but it really seems better with it. To
            # see the real difference, compare cmd_t / mw_angle_alt_scale to
            # cmd_t * mw_angle_alt_scale and see how it sinks. That happens to
            # a less noticeable degree with no modification.
            cmd_t = cmd_t / max(0.5, self.throttle.mw_angle_alt_scale)

        # Print statements for the low and high i components
        # print "Roll  low, hi:", self.roll_low._i, self.roll._i
        # print "Pitch low, hi:", self.pitch_low._i, self.pitch._i
        # print "Throttle low, hi:", self.throttle_low._i, self.throttle._i
        return [cmd_r, cmd_p, cmd_y, cmd_t]
