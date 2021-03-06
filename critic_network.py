
import tensorflow as tf 
import numpy as np
import math
from detector import Detector
from program import Program
from message_passing import Message_passing

LAYER1_SIZE = 500
LAYER2_SIZE =400
LEARNING_RATE = 1e-3
TAU = 0.001
L2 = 0.01

class CriticNetwork:
    """docstring for CriticNetwork"""
    def __init__(self,sess,state_dim,action_dim):
        self.time_step = 0
        self.sess = sess
        # create q network
        self.state_input,\
        self.action_input,\
        self.q_value_output,\
        self.net = self.create_q_network(state_dim,action_dim)

        # create target q network (the same structure with q network)
        self.target_state_input,\
        self.target_action_input,\
        self.target_q_value_output,\
        self.target_update = self.create_target_q_network(state_dim,action_dim,self.net)

        self.create_training_method()

        # initialization 
        self.sess.run(tf.global_variables_initializer())
            
        self.update_target()

    def create_training_method(self):
        # Define training optimizer
        self.y_input = tf.placeholder("float",[None,1])
        weight_decay = tf.add_n([L2 * tf.nn.l2_loss(var) for var in self.net])
        self.cost = tf.reduce_mean(tf.square(self.y_input - self.q_value_output)) + weight_decay
        self.optimizer = tf.train.AdamOptimizer(LEARNING_RATE).minimize(self.cost)
        self.action_gradients = tf.gradients(self.q_value_output,self.action_input)

    def create_q_network(self,state_dim,action_dim):
        # the layer size could be changed
        layer1_size = LAYER1_SIZE
        layer2_size = LAYER2_SIZE

        state_input = tf.placeholder("float",[None,state_dim])
        program_order = tf.placeholder("float",[None,4]);
        self.program_order = program_order;
        #detector
        self.detector=Detector(self.sess,state_dim,5,15,state_input,"_critic");
        Theta=self.detector.Theta;
        detector_params=self.detector.net;
        #program
        self.program=Program(self.sess,state_dim,5,15,Theta,program_order,"_critic");
        p=self.program.p;
        #message_passing
        self.message_passing=Message_passing(self.sess,state_dim,5,15,p,state_input,150,64,64,"_critic");
        state_input2 = self.message_passing.state_output;
        message_passing_params = self.message_passing.net;
        #get h
        state_input2 = tf.reshape(state_input2,[-1,5,150]);
        state_input2 = tf.unstack(state_input2,5,1);
        p=tf.unstack(p,5,1);
        h=0;
        for i in range(5):
          h+=tf.stack([p[i]]*150,1)*state_input2[i];
        action_input = tf.placeholder("float",[None,action_dim])

        W1 = self.variable([action_dim,150],action_dim)
        b1 = self.variable([150],action_dim)
        W2 = tf.Variable(tf.random_uniform([150,1],-3e-3,3e-3))
        b2 = tf.Variable(tf.random_uniform([1],-3e-3,3e-3))
        q_value_output = tf.matmul(tf.tanh(h+tf.matmul(action_input,W1)+b1),W2)+b2;
        params = detector_params+message_passing_params+[W1,b1,W2,b2];
        
        return state_input,action_input,q_value_output,params

    def create_target_q_network(self,state_dim,action_dim,net):
        state_input = tf.placeholder("float",[None,state_dim])
        program_order = tf.placeholder("float",[None,4]);
        self.target_program_order = program_order;
        action_input = tf.placeholder("float",[None,action_dim])
        ema = tf.train.ExponentialMovingAverage(decay=1-TAU)
        target_update = ema.apply(net)
        target_net = [ema.average(x) for x in net]

        # params for each net
        d_net=target_net[:self.detector.params_num];
        m_net=target_net[self.detector.params_num:(self.detector.params_num+self.message_passing.params_num)];
        c_net=target_net[(self.detector.params_num+self.message_passing.params_num):];
        # run detector
        Theta=self.detector.run_target_nets(state_input,d_net);
        # run program
        p=self.program.run_target_nets(Theta,program_order);
        # run message_passing
        state_input2=self.message_passing.run_target_nets(state_input,p,m_net);
        #get h
        state_input2 = tf.reshape(state_input2,[-1,5,150]);
        state_input2 = tf.unstack(state_input2,5,1);
        p=tf.unstack(p,5,1);
        h=0;
        for i in range(5):
          h+=tf.stack([p[i]]*150,1)*state_input2[i];

        q_value_output = tf.matmul(tf.tanh(h+tf.matmul(action_input,c_net[0])+c_net[1]),c_net[2])+c_net[3];

        return state_input,action_input,q_value_output,target_update

    def update_target(self):
        self.sess.run(self.target_update)

    def train(self,y_batch,state_batch,action_batch,program_order_batch):
        self.time_step += 1
        self.sess.run(self.optimizer,feed_dict={
            self.y_input:y_batch,
            self.state_input:state_batch,
            self.program_order:program_order_batch,
            self.action_input:action_batch
            })

    def gradients(self,state_batch,action_batch,program_order_batch):
        return self.sess.run(self.action_gradients,feed_dict={
            self.state_input:state_batch,
            self.program_order:program_order_batch,
            self.action_input:action_batch
            })[0]

    def target_q(self,state_batch,action_batch,program_order_batch):
        return self.sess.run(self.target_q_value_output,feed_dict={
            self.target_state_input:state_batch,
            self.target_program_order:program_order_batch,
            self.target_action_input:action_batch
            })

    def q_value(self,state_batch,action_batch,program_order_batch):
        return self.sess.run(self.q_value_output,feed_dict={
            self.state_input:state_batch,
            self.program_order:program_order_batch,
            self.action_input:action_batch})

    # f fan-in size
    def variable(self,shape,f):
        return tf.Variable(tf.random_uniform(shape,-1/math.sqrt(f),1/math.sqrt(f)))
'''
    def load_network(self):
        self.saver = tf.train.Saver()
        checkpoint = tf.train.get_checkpoint_state("saved_critic_networks")
        if checkpoint and checkpoint.model_checkpoint_path:
            self.saver.restore(self.sess, checkpoint.model_checkpoint_path)
            print "Successfully loaded:", checkpoint.model_checkpoint_path
        else:
            print "Could not find old network weights"

    def save_network(self,time_step):
        print 'save critic-network...',time_step
        self.saver.save(self.sess, 'saved_critic_networks/' + 'critic-network', global_step = time_step)
'''
        
