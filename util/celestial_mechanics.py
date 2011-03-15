# celestial_mechanics.py
#   celestial mechanics utilities for exoplanet ephemerides
#
# intellectual property:
#   Copyright 2009 David W. Hogg.  All rights reserved.	 Watch this space
#   for an open-source license to be inserted later.
#
# comments:
#   - Written for clarity, not speed.  The code is intended to be human-
#     readable.
#
# bugs:
#   - Need to make Fourier expansion functions.
#	- What to do if e is close to 1.0 in eccentric_anomaly
#

from math import pi
import unittest
import sys

import numpy
import numpy as np
from numpy import *
from scipy.special import jn
import matplotlib.pyplot as plt

from astrometry.util.starutil_numpy import *

ihat = array([1.,0.,0.])
jhat = array([0.,1.,0.])
khat = array([0.,0.,1.])
default_tolerance = 1e-15 # (radians) don't set to zero or less
default_maximum_iteration = 1000 # should never hit this limit!
default_order = 32
default_K = 1.0

(Equinox, Solstice, EclipticPole) = ecliptic_basis()

c_au_per_yr = 63239.6717 # google says

def norm(x):
	return np.sqrt(np.dot(x, x))

def deg2rad(x):
	return x * pi/180.
	#return radians(x)

def orbital_elements_to_xyz(E, observer, light_travel=True):
	(a,e,i,Omega,pomega,M,GM) = E
	# ugh, it's hard to be units-agnostic.
	assert(GM == 2.95912e-04)
	# orbital angular velocity  [radians/yr]
	meanfrequency = np.sqrt(GM / a**3)
	# Correct for light-time delay.
	dM = 0.
	lastdM = dM
	for ii in range(100):
		(x,v) = phase_space_coordinates_from_orbital_elements(a,e,i,Omega,pomega,M-dM,GM)
		dx = (x - observer)
		if not light_travel:
			break
		r = norm(dx)
		travel = r / c_au_per_yr
		dM = travel * meanfrequency
		if abs(lastdM - dM) < 1e-12:
			break
		lastdM = dM
	#print 'niters', ii
	dx /= norm(dx)
	edx = dx[0] * Equinox + dx[1] * Solstice + dx[2] * EclipticPole
	return edx

# E = (a,e,i,Omega,pomega,M, GM)
# observer = 3-vector
# light_travel: correct for light travel time?
# Returns Ra,Dec in degrees.
def orbital_elements_to_radec(E, observer, light_travel=True):
	xyz = orbital_elements_to_xyz(E, observer, light_travel)
	return xyztoradec(xyz)

# convert orbital elements into vectors in the plane of the orbit.
def orbital_vectors_from_orbital_elements(i, Omega, pomega):
	ascendingnodevector = np.cos(Omega) * ihat + np.sin(Omega) * jhat
	tmpydir= np.cross(khat, ascendingnodevector)
	zhat= np.cos(i) * khat - np.sin(i) * tmpydir
	tmpydir= np.cross(zhat, ascendingnodevector)
	xhat= np.cos(pomega) * ascendingnodevector + np.sin(pomega) * tmpydir
	yhat = np.cross(zhat, xhat)
	return (xhat, yhat, zhat)

def position_from_orbital_vectors(xhat, yhat, a, e, M):
	E = eccentric_anomaly_from_mean_anomaly(M, e)
	cosE = np.cos(E)
	sinE = np.sin(E)
	b = a*np.sqrt(1. - e**2)
	x =  a * (cosE - e)  * xhat + b * sinE        * yhat
	return x

# convert orbital elements to phase-space coordinates
#  a       - semi-major axis (length units)
#  e       - eccentricity
#  i       - inclination (rad)
#  Omega   - longitude of ascending node (rad)
#  pomega  - argument of periapsis (rad)
#  M       - mean anomaly (rad)
#  GM      - Newton's constant times central mass (length units cubed over time units squared)
#  return  - (x,v)
#            position, velocity (length units, length units per time unit)
def phase_space_coordinates_from_orbital_elements(a, e, i, Omega, pomega, M, GM):
	(xhat, yhat, zhat) = orbital_vectors_from_orbital_elements(i, Omega, pomega)
	dMdt = np.sqrt(GM / a**3)
	E = eccentric_anomaly_from_mean_anomaly(M, e)
	cosE = np.cos(E)
	sinE = np.sin(E)
	dEdt = 1.0 / (1.0 - e * cosE) * dMdt
	b = a*np.sqrt(1. - e**2)
	x =  a * (cosE - e)  * xhat + b * sinE        * yhat
	v = -a * sinE * dEdt * xhat + b * cosE * dEdt * yhat
	return (x, v)

class UnboundOrbitError(ValueError):
	pass

def energy_from_phase_space_coordinates(x, v, GM):
	return 0.5 * np.dot(v, v) - GM / norm(x)

# convert phase-space coordinates to orbital elements
#  x       - position (3-vector, length units)
#  v       - velocity (3-vector, length units per time unit)
#  GM      - Newton's constant times central mass (length units cubed over time units squared)
#  return  - (a, e, i, Omega, pomega, M)
#          - see "phase_space_coordinates" for definitions
def orbital_elements_from_phase_space_coordinates(x, v, GM):
	energy = energy_from_phase_space_coordinates(x, v, GM)
	if energy > 0:
		raise UnboundOrbitError('orbital_elements_from_phase_space_coordinates: Unbound orbit')

	angmom = np.cross(x, v)
	zhat = angmom / norm(angmom)
	evec = np.cross(v, angmom) / GM - x / norm(x)
	e = norm(evec)
	if e == 0:
		# by convention:
		xhat = np.cross(jhat, zhat)
		xhat /= norm(xhat)
	else:
		xhat = evec / e
	yhat = np.cross(zhat, xhat)
	a = -0.5 * GM / energy
	dMdt = np.sqrt(GM / a**3)
	i = np.arccos(angmom[2] / norm(angmom))
	if i == 0:
		Omega = 0.0
	else:
		Omega = np.arctan2(angmom[1], angmom[0]) + 0.5 * pi
		if Omega < 0:
			Omega += 2.*pi
		if i < 0:
			i *= -1.
			Omega += pi
	cosOmega = cos(Omega)
	sinOmega = sin(Omega)
	if e == 0:
		pomega = 0. - Omega
	else:
		pomega = arccos(min(1.0, (evec[0] * cosOmega + evec[1] * sinOmega) / e))
	horriblescalar = ( sinOmega * evec[2] * angmom[0]
			 - cosOmega * evec[2] * angmom[1]
			 + cosOmega * evec[1] * angmom[2]
			 - sinOmega * evec[0] * angmom[2])
	if horriblescalar < 0.:
		pomega = 2.0 * pi - pomega
	if pomega < 0.0:
		pomega += 2.0 * pi
	if pomega > 2.0 * pi:
		pomega -= 2.0 * pi
	f = np.arctan2(np.dot(yhat, x), np.dot(xhat, x))
	M = mean_anomaly_from_true_anomaly(f, e)
	if M < 0:
		M += 2.*pi
	return (a, e, i, Omega, pomega, M)

# convert eccentric anomaly to mean anomaly
#  E       - eccentric anomaly (radians)
#  e       - eccentricity
#  return  - mean anomaly (radians)
def mean_anomaly_from_eccentric_anomaly(E, e):
	return (E - e * np.sin(E))

def mean_anomaly_from_true_anomaly(f, e):
	return mean_anomaly_from_eccentric_anomaly(eccentric_anomaly_from_true_anomaly(f, e), e)

# convert mean anomaly to eccentric anomaly
#  M       - [array of] mean anomaly (radians)
#  e       - eccentricity
#  [tolerance - read the source]
#  [maximum_iteration - read the source]
#  return  - eccentric anomaly (radians)
def eccentric_anomaly_from_mean_anomaly(M, e, tolerance = default_tolerance,
		      maximum_iteration = default_maximum_iteration, verbose=False):
	E = M + e * np.sin(M)
	iteration = 0
	deltaM = 100.0
	while (iteration < maximum_iteration) and (abs(deltaM) > tolerance):
		deltaM = (M - mean_anomaly_from_eccentric_anomaly(E, e))
		E = E + deltaM / (1. - e * cos(E))
		iteration += 1
	if verbose: print 'eccentric anomaly iterations:',iteration
	return E

def eccentric_anomaly_from_true_anomaly(f, e):
	E = np.arccos((np.cos(f) + e) / (1.0 + e * np.cos(f)))
	E *= (np.sign(np.sin(f)) * np.sign(np.sin(E)))
	return E

# convert eccentric anomaly to true anomaly
#  E       - eccentric anomaly (radians)
#  e       - eccentricity
#  return  - true anomaly (radians)
def true_anomaly_from_eccentric_anomaly(E, e):
	f = np.arccos((np.cos(E) - e) / (1.0 - e * np.cos(E)))
	f *= (np.sign(np.sin(f)) * np.sign(np.sin(E)))
	return f

# compute radial velocity
#  K       - radial velocity amplitude
#  f       - true anomaly (radians)
#  e       - eccentricity
#  pomega  - eccentric longitude (radians)
#  return  - radial velocity (same units as K)
def radial_velocity(K, f, e, pomega):
	return K * (np.sin(f + pomega) + e * np.sin(pomega))

# compute radial velocity
#  K       - radial velocity amplitude
#  M       - mean anomaly (radians)
#  e       - eccentricity
#  pomega  - eccentric longitude (radians)
#  return  - radial velocity (same units as K)
def radial_velocity_from_M(K, M, e, pomega):
	E = M + e*np.sin(M)
	term1 = np.cos(pomega) * np.sqrt(1 - e**2) * np.sin(E) / (1 - e*np.cos(E))
	term2 = np.sin(pomega) * (np.cos(E) - e) / (1 - e*np.cos(E))
	term3 = e*np.sin(pomega)
	return K * (term1 + term2 + term3)

# compute radial velocity using a truncated Fourier series
#  K       - radial velocity amplitude
#  M       - mean anomaly (radians) APW: you may want to change this input
#  e       - eccentricity
#  pomega  - eccentric longitude (radians)
#  phi	   - phase
#  [order  - read the source]
#  return  - radial velocity (same units as K)
def radial_velocity_fourier_series(K, M, e, pomega, phi, order=default_order):
	vr = 0.0
	for n in arange(0, order+1, 1):
		vr += K*(fourier_coeff_A(n, pomega, phi, e) * np.cos(n*(M-phi)) \
			+ fourier_coeff_B(n, pomega, phi, e) * np.sin(n*(M-phi)))
	return vr

# the following is based on the naming convention in Itay's notes on Fourier analysis
#  - fourier_coeff_A and fourier_coeff_B are the actual coefficients in the series
#  - aprime and bprime are just used to simplify the code, and break it up to make it more readable

#  n       - order of the coefficient
#  e       - eccentricity
def aprime(n,e):
	return np.sqrt(1. - e**2)*( ((np.sqrt(1. - e**2) - 1)/e)*jn(n,n*e) + jn(n-1,n*e))

def bprime(n,e):
	return np.sqrt(1. - e**2)*( ((np.sqrt(1. - e**2) - 1)/e)*jn(n,n*e) - jn(n-1,n*e))

def fourier_coeff_A(n, pomega, phi, e):
	return 0.5 * (aprime(n,e) * np.sin(pomega + n * phi) + bprime(n,e) * np.sin(pomega - n * phi))

def fourier_coeff_B(n, pomega, phi, e):
	return 0.5 * (aprime(n,e) * np.cos(pomega + n * phi) - bprime(n,e) * np.cos(pomega - n * phi))

# APW: adjust function call as necessary
#  return  - amplitudes as a list of tuples (An,Bn)
def radial_velocity_fourier_amplitudes(K, phi, e, pomega, order=default_order):
	amplitudes = []
	for n in range(order):
		amplitudes.append((fourier_coeff_A(n, pomega, phi, e), fourier_coeff_B(n, pomega, phi, e)))
	return amplitudes

def eccentricity_from_fourier_amplitudes(amplitudes):
	K = np.sqrt(amplitude[0]**2 + amplitude[1]**2)
	phi = np.arctan(amplitude[1] / amplitude[0]) # WRONG?
	e = 0 # WRONG
	pomega = 0 # WRONG
	return (K, phi, e, pomega)

	

# some functional testing
if __name__ == '__main__':
	from test_celestial_mechanics import *
	#suite = unittest.TestLoader().loadTestsFromTestCase(TestOrbitalElements)

	suite = unittest.TestSuite()
	#suite.addTest(TestOrbitalElements('testEdgeCases'))
	suite.addTest(TestOrbitalElements('testAgainstJPL_2'))

	unittest.TextTestRunner(verbosity=2).run(suite)
	import sys
	sys.exit(0)
	
	# -- test Earth ephemeris against JPL at Holmes' closest approach
	# -- test Holmes against JPL         ---------''------------
	# -- test direction2radec()

	try:
		arg1 = sys.argv[1]
	except IndexError:
		arg1 = 0
	
	for e in [0.01, 0.1, 0.9, 0.99, 0.999]:
		print 'eccentricity:', e
		M = arange(-3.16,-3.14,0.001) # easy
		#M = arange(-10., 10., 2.1)    # easy
		#M = arange(-0.01,0.01,0.001)  # hard
		print 'mean anomaly input:', M
		E = eccentric_anomaly_from_mean_anomaly(M, e, verbose=True)
		print 'eccentric anomaly output:', E
		f = true_anomaly_from_eccentric_anomaly(E, e)
		print 'true anomaly output:', f
		M2 = mean_anomaly_from_eccentric_anomaly(E, e)
		print 'round-trip error:', M2 - M
	
	if arg1 == "plot":
		# This code will do the plotting:
		range_min = 0.0
		range_max = 20.0
		step_size = 0.01
		phase = 0.0
		pomegas = [0.0, pi/5., 3.*pi/5., 5.*pi/5., 7.*pi/5., 9.*pi/5.]
		pomegas_str = ["pomega = $0.0$", "pomega = $\pi/5$", "pomega = $3\pi/5$", "pomega = $\pi$", \
			"pomega = $7\pi/5$", "pomega = $9\pi/5$"]
		eccens = [0.01, 0.1, 0.5, 0.9, 0.99]
		orders = [2, 4, 8, 16, 32]
		M = arange(range_min,range_max,step_size)
		
		for n in orders:
			for e in eccens:
				i = 1
				for pomega in pomegas:
					plt.clf()
					plt.suptitle(pomegas_str[i-1] + ", e = %.2f, n = %i" % (e,n))
					plt.subplot(211)
					plt.plot(M, radial_velocity_fourier_series(default_K, M, e, pomega, phase, order=n), 'r')
					plt.plot(M, radial_velocity_from_M(default_K, M, e, pomega), 'k--') 
					plt.axis([range_min,range_max,-(default_K+1.),default_K+1.])
					plt.subplot(212)
					plt.plot(M, radial_velocity_from_M(default_K, M, e, pomega) \
						- radial_velocity_fourier_series(default_K, M, e, pomega, phase, order=n), 'k')
					plt.savefig("celestial_mechanics_plots/pomega_%i_e_%.2f_n_%i.png" % (i,e,n))
					i += 1