import argparse
import subprocess
from pathlib import Path
import pickle
import numpy as np
from alphafold.Data.pipeline import DataPipeline as MonomerPipeline
from alphafold.Model import AlphaFold, AlphaFoldFeatures, model_config
import torch
import numpy as np
import matplotlib.pylab as plt

if __name__ == '__main__':
	parser = argparse.ArgumentParser(description='Train deep protein docking')	
	parser.add_argument('-fasta_path', default='T1024.fas', type=str)
	parser.add_argument('-output_dir', default='/media/lupoglaz/AlphaFold2Output', type=str)
	parser.add_argument('-model_name', default='model_1', type=str)
	parser.add_argument('-data_dir', default='/media/lupoglaz/AlphaFold2Data', type=str)
		
	args = parser.parse_args()
		
	model_config = model_config(args.model_name)
	model_config.data.eval.num_ensemble = 1
	model_config.data.common.use_templates = False
	af2features = AlphaFoldFeatures(config=model_config)

	features_path = Path(args.output_dir)/Path('T1024')/Path('features.pkl')
	proc_features_path = Path(args.output_dir)/Path('T1024')/Path('proc_features.pkl')
	with open(features_path, 'rb') as f:
		raw_feature_dict = pickle.load(f)
	with open(proc_features_path, 'rb') as f:
		af2_proc_features = pickle.load(f)
	
	this_proc_features = af2features(raw_feature_dict, random_seed=42)
	
	common_keys = set(af2_proc_features.keys()) & set(this_proc_features.keys())
	missing_keys = set(af2_proc_features.keys()) - common_keys
	print(missing_keys)
	for k in common_keys:
		if k.startswith('template_'):
			continue
		print(k, af2_proc_features[k].shape, this_proc_features[k].shape)