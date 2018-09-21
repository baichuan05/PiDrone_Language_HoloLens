#!/usr/bin/env python
import rospy

# swap these two lines to switch to the new multiwii.
#from pyMultiwii import MultiWii
from h2rMultiWii import MultiWii  


from sys import stdout
from geometry_msgs.msg import PoseStamped, Point
from sensor_msgs.msg import Imu
from pidrone_pkg.msg import RC
import sys
import tf
import numpy as np
import time
import math
from visualization_msgs.msg import Marker

board = MultiWii("/dev/ttyACM0")
        

cmds = [1500, 1500, 1500, 1000, 1500, 1500, 1500, 1500]
int_pose = PoseStamped()
int_vel = [0, 0, 0]
int_pos = [0, 0, 0]

millis = lambda: int(round(time.time() * 1000))

# rotate vector v1 by quaternion q1 
def qv_mult(q1, v1):
    v1 = tf.transformations.unit_vector(v1)
    q2 = list(v1)
    q2.append(0.0)
    return tf.transformations.quaternion_multiply(
        tf.transformations.quaternion_multiply(q1, q2), 
        tf.transformations.quaternion_conjugate(q1)
    )[:3]

def att_pub():
    global cmds
    imupub = rospy.Publisher('/pidrone/imu', Imu, queue_size=1, tcp_nodelay=False)
    intposepub = rospy.Publisher('/pidrone/int_pose', PoseStamped, queue_size=1, tcp_nodelay=False)
    markerpub = rospy.Publisher('/pidrone/imu_visualization_marker', Marker, queue_size=1, tcp_nodelay=False)

    rate = rospy.Rate(100)
    imu = Imu()
    marker = Marker()
    board.arm()
    print("armed")
    prev_time = rospy.Time.now()
    br = tf.TransformBroadcaster()
    seq = 0

    import rospkg
    import yaml
    rospack = rospkg.RosPack()
    path = rospack.get_path('pidrone_pkg')
    f = open("%s/params/multiwii.yaml" % path)
    means = yaml.load(f)
    f.close()
    print "means", means
    accRawToMss = 9.8 / means["az"]
    accZeroX = means["ax"] * accRawToMss
    accZeroY = means["ay"] * accRawToMss
    accZeroZ = means["az"] * accRawToMss

    try:
        att_data = board.getData(MultiWii.ATTITUDE)
        imu_data = board.getData(MultiWii.RAW_IMU)
        #board.sendCMD(0, MultiWii.ATTITUDE, [])
        #board.sendCMD(0, MultiWii.RAW_IMU, [])

        while not rospy.is_shutdown():

            att_data, imu_data = board.getDataBulk([
                (MultiWii.ATTITUDE, []),
                (MultiWii.RAW_IMU, []),
            ])

            #att_data = board.receiveDataPacket()
            #imu_data = board.receiveDataPacket()
            #board.sendCMD(0, MultiWii.ATTITUDE, [])
            #board.sendCMD(0, MultiWii.RAW_IMU, [])

            
            #att_data = board.getData(MultiWii.ATTITUDE)
            #imu_data = board.getData(MultiWii.RAW_IMU, fast=True)
            #print cmds[0], cmds[1], cmds[2], cmds[3], att_data
            #print "imu", imu_data
            board.sendCMD(16, MultiWii.SET_RAW_RC, cmds)


            # message = "angx = {:+.2f} \t angy = {:+.2f} \t heading = {:+.2f} \t elapsed = {:+.4f} \t".format(float(board.attitude['angx']),float(board.attitude['angy']),float(board.attitude['heading']),float(board.attitude['elapsed']))
            # stdout.write("\r%s" % message )
            # stdout.flush()
            # End of fancy printing

            roll = board.attitude['angx']
            pitch = board.attitude['angy']
            yaw = board.attitude['heading']
            quaternion = tf.transformations.quaternion_from_euler(roll * 2 * math.pi / 360, pitch * 2 * math.pi / 360, 0)
            # print(roll, pitch, yaw, quaternion)
            imu.header.frame_id = "base"
            imu.orientation.x = quaternion[0]
            imu.orientation.y = quaternion[1]
            imu.orientation.z = quaternion[2]
            imu.orientation.w = quaternion[3]
            imu.linear_acceleration.x = board.rawIMU['ax'] * accRawToMss - accZeroX 
            imu.linear_acceleration.y = board.rawIMU['ay'] * accRawToMss - accZeroY 
            imu.linear_acceleration.z = board.rawIMU['az'] * accRawToMss - accZeroZ
            imupub.publish(imu)

            marker.header.stamp = rospy.Time.now()
            marker.header.frame_id = "/base"
            marker.type = Marker.CUBE
            marker.action = 0
            marker.pose.orientation = imu.orientation
            marker.pose.position.x = imu.linear_acceleration.x * 0.1
            marker.pose.position.y = imu.linear_acceleration.y * 0.1
            marker.pose.position.z = imu.linear_acceleration.z * 0.1
            #marker.points.append(Point(0, 0, 0))
            #marker.points.append(Point(imu.linear_acceleration.x * 1,
            #                           imu.linear_acceleration.y * 1,
            #                           imu.linear_acceleration.z * 1))


            marker.id = 0
            marker.lifetime = rospy.Duration(10)
            marker.scale.x = 0.1
            marker.scale.y = 0.1
            marker.scale.z = 0.1
            marker.color.r = 1
            marker.color.g = 1
            marker.color.b = 1
            marker.color.a = 1
            markerpub.publish(marker)
            
            #print "imu", imu.linear_acceleration

            # Integrate the things
            #rotated_accel = qv_mult(quaternion, np.array([imu.linear_acceleration.x,
            #imu.linear_acceleration.y, imu.linear_acceleration.z]))
            rotated_accel = np.array([imu.linear_acceleration.x, imu.linear_acceleration.y, imu.linear_acceleration.z])

            curr_time = rospy.Time.now()
            duration = curr_time - prev_time
            duration_seconds = duration.to_sec()
            #print "duration", duration_seconds
            for i in range(len(int_vel)):
                int_vel[i] += rotated_accel[i] * duration_seconds
                int_pos[i] += int_vel[i] * duration_seconds
            prev_time = curr_time
            int_pose.header.seq = seq
            seq+=1 
            int_pose.header.stamp = curr_time
            int_pose.header.frame_id = "base"
            int_pose.pose.orientation = imu.orientation
            int_pose.pose.position.x = int_pos[0]
            int_pose.pose.position.y = int_pos[1]
            int_pose.pose.position.z = int_pos[2]
            
            intposepub.publish(int_pose)
            #print "pose", int_pose.pose.position
            rate.sleep()
    finally:
        print "disarming"
        board.disarm()


def cmd_call(data):
    cmds[0] = data.roll
    cmds[1] = data.pitch
    cmds[2] = data.yaw
    cmds[3] = data.throttle
    cmds[4] = 1900
    cmds[5] = data.aux2
    cmds[6] = data.aux3
    cmds[7] = data.aux4



def main():
    rospy.init_node('multiwii')
    try:
        rospy.Subscriber("/pidrone/commands", RC, cmd_call)
        att_pub()


    except rospy.ROSInterruptException:
        pass


if __name__ == "__main__":
    main()
