import json
import argparse
import torch
import torch.nn as nn
import time
from encoder_decoder import BasicBlock, Lpt2NbodyNet
from discriminator import LPT2NbodyDiscriminator
from data_utils import SimuData
from torch.utils.data import DataLoader
from cgan import CGAN
import numpy as np

# python reconLPT2Nbody_cGAN.py --config_file_path configs/config.json

def get_parser():
	parser = argparse.ArgumentParser(description="CGAN for LPT2Nbody network")
	parser.add_argument('--config_file_path', type=str, default='')
	return parser

if __name__ == "__main__":
	parser = get_parser()
	args = parser.parse_args()
	with open(args.config_file_path) as f:
		configs = json.load(f)

	generator = Lpt2NbodyNet(BasicBlock, [3, 3])
	generator.cuda()
	l2_criterion = nn.MSELoss()
	entropy_criterion = nn.BCELoss()
	base_data_path = configs["base_data_path"]
	output_path = configs["output_path"]
	in_channels = 6 if configs["train"]["cgan"]["conditioning"] else 3
	discriminator = LPT2NbodyDiscriminator(BasicBlock, [3, 3, 3], in_channels)
	discriminator.cuda()

	TrainSet = SimuData(base_data_path,
						configs['train']['data_partition']['lIndex'],
						configs['train']['data_partition']['hIndex'],
						configs['train']['data_partition']['aug'])
	ValSet = SimuData(base_data_path,
						configs['val']['data_partition']['lIndex'],
						configs['val']['data_partition']['hIndex'],
						configs['val']['data_partition']['aug'])
	TestSet = SimuData(base_data_path,
						configs['test']['data_partition']['lIndex'],
						configs['test']['data_partition']['hIndex'],
						configs['test']['data_partition']['aug'])
	TrainLoader = DataLoader(TrainSet,
								batch_size=configs['train']['batch_size'],
								shuffle=True,
								num_workers=configs['train']['num_workers'])
	ValLoader   = DataLoader(ValSet,
								batch_size=configs['val']['batch_size'],
								shuffle=False,
								num_workers=configs['train']['num_workers'])
	TestLoader  = DataLoader(TestSet,
								batch_size=configs['test']['batch_size'],
								shuffle=False,
								num_workers=configs['train']['num_workers'])
	net = CGAN(
		generator,
		discriminator,
		configs["train"]["cgan"]
	)
	eval_frequency = configs["train"]["eval_frequency"]
	loss_val = []
	best_validation_accuracy = 100

	for _ in range(configs['train']['num_epoches']):
		for t, data in enumerate(TrainLoader, 0):
			start_time = time.time()
			batch_x = torch.autograd.Variable(data[0], requires_grad=False).cuda()
			batch_y = torch.autograd.Variable(data[1], requires_grad=False).cuda()
			net.train()
			net.train_discriminator_step(batch_x, batch_x, batch_y)
			net.train_generator_step(batch_x,
				batch_y,
				extra_loss=l2_criterion,
				extra_loss_fraction=configs["train"]["cgan"]["extra_loss_fraction"])
			if (t != 0 and t % eval_frequency == 0):
				net.eval()
				start_time = time.time()
				_loss = 0
				for t_val, data in enumerate(ValLoader,0):
					g_batch_x = torch.autograd.Variable(data[0],requires_grad=False,volatile=True).cuda()
					y_pred = net.forward_generator(g_batch_x)
					_loss += l2_criterion(y_pred, torch.autograd.Variable(data[1],requires_grad=False).cuda()).data[0]
				loss_val.append(_loss/t_val)		
				np.savetxt(output_path+'valLoss.txt',loss_val)
				print ('valid: ' + str(_loss/t_val))
				"""
				if( _loss/t_val < best_validation_accuracy):
					torch.save(net,output_path+'BestModel.pt')
				if(iterTime%500==0 and iterTime!=0):
					torch.save(net,output_path+'BestModel'+str(iterTime)+'.pt')
				"""
			print(t)

