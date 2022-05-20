import functools
import collections
from typing import Tuple, Sequence

import torch
import numpy as np

Vecs = collections.namedtuple('Vecs', ['x', 'y', 'z'])
Rots = collections.namedtuple('Rots', [	'xx', 'xy', 'xz',
										'yx', 'yy', 'yz',
										'zx', 'zy', 'zz'])
Rigids = collections.namedtuple('Rigids', ['rot', 'trans'])


def vecs_apply(func, *args:Sequence[Vecs]) -> Vecs:
	return Vecs(func(*[arg.x for arg in args]), func(*[arg.y for arg in args]), func(*[arg.z for arg in args]))

def rots_apply(func, *args:Sequence[Rots]) -> Rots:
	return Rots(func(*[arg.xx for arg in args]), func(*[arg.xy for arg in args]), func(*[arg.xz for arg in args]),
				func(*[arg.yx for arg in args]), func(*[arg.yy for arg in args]), func(*[arg.yz for arg in args]),
				func(*[arg.zx for arg in args]), func(*[arg.zy for arg in args]), func(*[arg.zz for arg in args]))

def rigids_apply(func, *args:Sequence[Rigids]) -> Rigids:
	return Rigids(rots_apply(func, *[arg.rot for arg in args]), vecs_apply(func, *[arg.trans for arg in args]))

def rigids_to_tensor_flat12(r:Rigids) -> torch.Tensor:
	return torch.stack(list(r.rot) + list(r.trans), dim=-1)

def rigids_from_tensor_flat12(t:torch.Tensor) -> Rigids:
	assert t.size(-1) == 12
	x = t.moveaxis(-1, 0)
	return Rigids(Rots(*x[:9]), Vecs(*x[9:]))

def rigids_from_tensor4x4(m:torch.Tensor) -> Rigids:
	assert m.size(-1) == 4
	assert m.size(-2) == 4
	return Rigids(	Rots(	m[..., 0, 0], m[..., 0, 1], m[..., 0, 2],
							m[..., 1, 0], m[..., 1, 1], m[..., 1, 2],
							m[..., 2, 0], m[..., 2, 1], m[..., 2, 2]),
					Vecs(	m[..., 0, 3], m[..., 1, 3], m[..., 2, 3]))

def rigids_from_3_points(point_on_neg_axis:Vecs, origin:Vecs, point_on_xy_plane:Vecs):
	m = rots_from_two_vecs(e0_unnormalized = vecs_sub(origin, point_on_neg_axis),
							e1_unnormalized = vecs_sub(point_on_xy_plane, origin))
	return Rigids(rot=m, trans=origin)

def vecs_from_tensor(x: torch.Tensor) -> Vecs:
	assert x.size(-1) == 3
	return Vecs(x[..., 0], x[..., 1], x[..., 2])

def vecs_to_tensor(v: Vecs) -> torch.Tensor:
	return torch.stack([v.x, v.y, v.z], dim=-1)

def vecs_squared_dist(v1:Vecs, v2:Vecs) -> torch.Tensor:
	return (torch.square(v1.x - v2.x) + torch.square(v1.y - v2.y) + torch.square(v1.z - v2.z))

def rots_mul_vecs(m:Rots, v:Vecs) -> Vecs:
	return Vecs(m.xx*v.x + m.xy*v.y + m.xz*v.z,
				m.yx*v.x + m.yy*v.y + m.yz*v.z,
				m.zx*v.x + m.zy*v.y + m.zz*v.z)

def rots_mul_rots(a:Rots, b:Rots) -> Rots:
	c0 = rots_mul_vecs(a, Vecs(b.xx, b.yx, b.zx))
	c1 = rots_mul_vecs(a, Vecs(b.xy, b.yy, b.zy))
	c2 = rots_mul_vecs(a, Vecs(b.xz, b.yz, b.zz))
	return Rots(c0.x, c1.x, c2.x, c0.y, c1.y, c2.y, c0.z, c1.z, c2.z)

def rots_invert(m:Rots) -> Rots:
	return Rots(m.xx, m.yx, m.zx,
				m.xy, m.yy, m.zy,
				m.xz, m.yz, m.zz)

def rots_from_two_vecs(e0_unnormalized:Vecs, e1_unnormalized:Vecs)->Rots:
	e0 = vecs_robust_normalize(e0_unnormalized)
	c = vecs_dot_vecs(e1_unnormalized, e0)
	e1 = Vecs(e1_unnormalized.x - c*e0.x, e1_unnormalized.y - c*e0.y, e1_unnormalized.z - c*e0.z)
	e1 = vecs_robust_normalize(e1)
	e2 = vecs_cross_vecs(e0, e1)
	return Rots(e0.x, e1.x, e2.x, e0.y, e1.y, e2.y, e0.z, e1.z, e2.z)

def rots_from_tensor3x3(m:torch.Tensor):
	assert m.size(-1) == 3
	assert m.size(-2) == 3
	return Rots(m[..., 0,0], m[..., 0,1], m[..., 0,2],
				m[..., 1,0], m[..., 1,1], m[..., 1,2],
				m[..., 2,0], m[..., 2,1], m[..., 2,2])


def vecs_add(a:Vecs, b:Vecs) -> Vecs:
	return Vecs(a.x+b.x, a.y+b.y, a.z+b.z)

def vecs_sub(a:Vecs, b:Vecs) -> Vecs:
	return Vecs(a.x-b.x, a.y-b.y, a.z-b.z)

def vecs_dot_vecs(a:Vecs, b:Vecs) -> torch.Tensor:
	return a.x * b.x + a.y * b.y + a.z * b.z

def vecs_cross_vecs(a:Vecs, b:Vecs) -> Vecs:
	return Vecs(a.y * b.z - a.z * b.y,
				a.z * b.x - a.x * b.z,
				a.x * b.y - a.y * b.x)

def vecs_robust_norm(a:Vecs, eps=1e-8) -> torch.Tensor:
	return torch.sqrt(torch.square(a.x) + torch.square(a.y) + torch.square(a.z) + eps)

def vecs_robust_normalize(a:Vecs) -> Vecs:
	norm = vecs_robust_norm(a)
	return Vecs(a.x/norm, a.y/norm, a.z/norm)

def rigids_mul_vecs(r:Rigids, v:Vecs) -> Rigids:
	return vecs_add(rots_mul_vecs(r.rot, v), r.trans)

def rigids_mul_rots(r:Rigids, m:Rots) -> Rigids:
	return Rigids(rots_mul_rots(r.rot, m), r.trans)

def rigids_mul_rigids(a:Rigids, b:Rigids) -> Rigids:
	return Rigids(rots_mul_rots(a.rot, b.rot), vecs_add(a.trans, rots_mul_vecs(a.rot, b.trans)))

def rigids_invert(r:Rigids) -> Rigids:
	inv_rots = rots_invert(r.rot)
	t = rots_mul_vecs(inv_rots, r.trans)
	inv_trans = Vecs(-t.x, -t.y, -t.z)
	return Rigids(inv_rots, inv_trans)

def quat_to_rot(quaternion):
	q0, q1, q2, q3 = quaternion[..., 0], quaternion[..., 1], quaternion[..., 2], quaternion[..., 3]
	return [[q0*q0+q1*q1-q2*q2-q3*q3, 	2*(q1*q2-q0*q3), 		2*(q0*q2+q1*q3)],
			[2*(q1*q2+q0*q3), 		q0*q0-q1*q1+q2*q2-q3*q3, 	2*(q2*q3-q0*q1)],
			[2*(q1*q3-q0*q2), 			2*(q0*q1+q2*q3), 	q0*q0-q1*q1-q2*q2+q3*q3]]

def apply_rot_to_vec(rot, vec, unstack:bool=False):
	x, y, z = [vec[:, i] for i in range(3)] if unstack else vec
	return [rot[0][0]*x + rot[0][1]*y + rot[0][2]*z,
			rot[1][0]*x + rot[1][1]*y + rot[1][2]*z,
			rot[2][0]*x + rot[2][1]*y + rot[2][2]*z]

def apply_inverse_rot_to_vec(rot, vec):
	x, y, z = vec
	return [rot[0][0]*x + rot[1][0]*y + rot[2][0]*z,
			rot[0][1]*x + rot[1][1]*y + rot[2][1]*z,
			rot[0][2]*x + rot[1][2]*y + rot[2][2]*z]


def quat_multiply_by_vec(quat, vec):
	a, b, c, d = tuple(quat[..., i] for i in range(4))
	l, m, n = tuple(vec[..., i] for i in range(3))
	return torch.stack([-b*l - c*m - d*n, a*l + c*n - d*m, a*m - b*n + d*l, a*n + b*m - c*l], dim=-1)

class QuatAffine(object):
	"""
	https://github.com/lupoglaz/alphafold/blob/2d53ad87efedcbbda8e67ab3be96af769dbeae7d/alphafold/model/quat_affine.py#L181
	"""
	def __init__(self, 	quaternion:torch.Tensor, translation:torch.Tensor, rotation:torch.Tensor=None, 
						normalize:bool=True, unstack_inputs:bool=False) -> None:
		super().__init__()
		if quaternion is not None:
			assert quaternion.shape[-1] == 4
			if normalize:
				quaternion = quaternion / torch.linalg.norm(quaternion, dim=-1, keepdim=True)
		if unstack_inputs:
			if rotation is not None:
				rotation = [torch.moveaxis(x, -1, 0) for x in torch.moveaxis(rotation, -2, 0)]
			translation = torch.moveaxis(translation, -1, 0)
		if rotation is None:
			rotation = quat_to_rot(quaternion)

		self.quaternion = quaternion
		self.rotation = [list(row) for row in rotation]
		self.translation = list(translation)
		# print(self.quaternion.dtype, self.rotation[0][0].dtype,self.translation[0].dtype)

		assert all(len(row) == 3 for row in self.rotation)
		assert len(self.translation) == 3

	@classmethod
	def from_tensor(cls, tensor:torch.Tensor, normalize:bool=False):
		return cls(tensor[...,:4], [tensor[...,4], tensor[...,5], tensor[...,6]], normalize=normalize)
	
	def to_tensor(self):
		return torch.cat([self.quaternion]+[x.unsqueeze(dim=-1) for x in self.translation], dim=-1)

	def scale_translation(self, position_scale):
		return QuatAffine(
		    quaternion=self.quaternion,
		    translation=[x * position_scale for x in self.translation],
		    rotation=[list(row) for row in self.rotation],
		    normalize=False,
		)
	
	def apply_rotation_tensor_fn(self, tensor_fn):
		return QuatAffine(
		    quaternion=tensor_fn(self.quaternion),
		    translation=list(self.translation),
		    rotation=[[tensor_fn(x) for x in row] for row in self.rotation],
		    normalize=False,
		)
	
	def apply_to_point(self, point, extra_dims=0):
		# r = self.rotation
		# t = self.translation
		r, t = [], []
		for t_i in self.translation:
			t_iu = t_i
			for _ in range(extra_dims):
				t_iu = t_iu.unsqueeze(dim=-1)
			t.append(t_iu)
		for r_i in self.rotation:
			r_vec = []
			for r_ij in r_i:
				r_iju = r_ij
				for _ in range(extra_dims):
					r_iju = r_iju.unsqueeze(dim=-1)
				r_vec.append(r_iju)
			r.append(r_vec)
		r_p = apply_rot_to_vec(r, point)
		return [r_p[0]+t[0], r_p[1]+t[1], r_p[2]+t[2]]

	def invert_point(self, transformed_point, extra_dims=0):
		# r = self.rotation
		# t = self.translation
		# for _ in range(extra_dims):
		# 	r = r.unsqueeze(dim=-1)
		# 	t = t.unsqueeze(dim=-1)
		r, t = [], []
		for t_i in self.translation:
			t_iu = t_i
			for _ in range(extra_dims):
				t_iu = t_iu.unsqueeze(dim=-1)
			t.append(t_iu)
		for r_i in self.rotation:
			r_vec = []
			for r_ij in r_i:
				r_iju = r_ij
				for _ in range(extra_dims):
					r_iju = r_iju.unsqueeze(dim=-1)
				r_vec.append(r_iju)
			r.append(r_vec)
		r_p = [transformed_point[0]-t[0], transformed_point[1]-t[1], transformed_point[2]-t[2]]
		return apply_inverse_rot_to_vec(r, r_p)

	def to_rigids(self) -> Rigids:
		r = self.rotation
		t = self.translation
		return Rigids(	Rots(	r[0][0], r[0][1], r[0][2],
								r[1][0], r[1][1], r[1][2],
								r[2][0], r[2][1], r[2][2]), 
						Vecs(t[0], t[1], t[2]))

	def cast_to(self, dtype=torch.float32):
		self.quaternion = self.quaternion.to(dtype=dtype)

		r, t = [], []
		for r_i in self.rotation:
			r_vec = [r_ij.to(dtype=dtype) for r_ij in r_i]
			r.append(r_vec)
		self.rotation = r

		t.extend(t_i.to(dtype=dtype) for t_i in self.translation)
		self.translation = t

	def pre_compose(self, update:torch.Tensor):
		vector_quaternion_update = update[...,:3]
		trans_update = [update[..., i] for i in range(3,6)]
		new_quaternion = self.quaternion + quat_multiply_by_vec(self.quaternion, vector_quaternion_update)
		trans_update = apply_rot_to_vec(self.rotation, trans_update)
		new_translation = [self.translation[i] + trans_update[i] for i in range(3)]
		return QuatAffine(new_quaternion, new_translation)