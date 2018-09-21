import rospy
import drone_MDP
from std_msgs.msg import Float32MultiArray, String
from geometry_msgs.msg import Point
import time
import load_drone_draggn
from i_draggn import ProgArgNet

ACTION_TABLE = {'forward': (0, 0.5, 0), 'back': (0, -0.5, 0), 'left': (-0.5, 0, 0), 'right': (0.5, 0, 0), 'up': (0, 0, 0.15), 'down': (0, 0, -0.15), 'take_photo': (-10,)}

command = ""
receive_command = False
# hololens
firstBox_pos = (-1, -1, -1)
secondBox_pos = (-1, -1, -1)
drone_pos = None
drone_path = Float32MultiArray()

def drone_callback(data):
    """
    Assume the space is 2 x 1.5 x 0.6 meters, a 4 x 3 x 2 grid
    """
    global drone_pos

    z = 0
    if data.z > 0.3:
        z = 1
    drone_pos = (int(data.x / 0.5), int(data.y / 0.5), z)

def box_callback(data):
    global firstBox_pos
    global secondBox_pos

    positions = (data.data).split()
    firstBox_pos = (int(positions[0]), int(positions[1]), int(positions[2]))
    secondBox_pos = (int(positions[3]), int(positions[4]), int(positions[5]))

def command_callback(data):
    global command
    global receive_command

    command = str(data.data)
    receive_command = True

rospy.init_node("path_pub")
pub = rospy.Publisher('/pidrone/path', Float32MultiArray, queue_size=1)
rospy.Subscriber("/pidrone/drone_position", Point, drone_callback)
rospy.Subscriber("/hololens/box_position", String, box_callback)
rospy.Subscriber("/hololens/language_command", String, command_callback)

time.sleep(3)
while True:

    if receive_command:
        receive_command = False
       
        print(drone_pos)
        print(command)

        if command == "take photo":
            block_color = 'photo'
            room_color = 'None'
        elif command == "go to room":
            block_color = 'None'
            if firstBox_pos[0] >= 0 and firstBox_pos[0] < 4 and firstBox_pos[1] == 0:
                room_color = 'red'
            if firstBox_pos[0] >= 0 and firstBox_pos[0] < 2 and firstBox_pos[1] >= 2 and secondBox_pos[1] < 4:
                room_color = 'green'
            if firstBox_pos[0] >= 3 and firstBox_pos[0] < 4 and firstBox_pos[1] >= 2 and secondBox_pos[1] < 4:
                room_color = 'blue'
        else:
            block_color = 'photo'
            if secondBox_pos[0] >= 0 and secondBox_pos[0] < 4 and secondBox_pos[1] == 0:
                room_color = 'red'
            if secondBox_pos[0] >= 0 and secondBox_pos[0] < 2 and secondBox_pos[1] >= 2 and secondBox_pos[1] < 4:
                room_color = 'green'
            if secondBox_pos[0] >= 3 and secondBox_pos[0] < 4 and secondBox_pos[1] >= 2 and secondBox_pos[1] < 4:
                room_color = 'blue'

        print("start goal")
        drone_MDP.run_no_speech(block_color, room_color, firstBox_pos, drone_pos, pub, drone_path)

    time.sleep(1)


