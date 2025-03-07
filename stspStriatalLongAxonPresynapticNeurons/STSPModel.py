import scipy as sc
import pylab as gr
output=sc.test('all',raise_warnings='release')
#import matplotlib as mpl
#mpl.use('gtkagg')
import matplotlib.pyplot as plt
#from mpl_toolkits.mplot3d import Axes3D
import scipy.io as sio
#import sympy as sy
import os
import time
#from analysis1 import GetLocalExtrema
gr.ion()
plt.ion()

#x, p= sy.symbols('x p')
#a, pa, r, xr= sy.symbols('a pa r xr')
#h= sy.symbols('h')

#dpAP = a*(pa-p) + h*(1-p) #= -p * (a+h) + (a*pa +h) 
#dxAP = r*x*(xr - x) + p*x
#dp = a*(p - pa) 
#dx = r*x*(xr - x) 

# Stimulus
if 0: 
    pars={'timeMin':-100.0, 'timeMax': 500.0, 'timeStep':1e-3,
      'tauX':75.0,  'tauP':75.0, 
      'asynX':1.0, 'asynP':0.3, 
      'kP':0.0, 'kX':1.0, 
      'jumpP':0.2, 
      'stimHz':20.0, 'stimStart':10.0}

#sampTimes=sc.arange(0,pars['timeMax'],pars['timeStep'])
#strHz=r'$\omega_{stim}$=%.0f Hz'%(pars['stimHz'])
#preSpikes=sc.arange(pars['stimStart'], pars['timeMax'], 1/pars['stimHz'])

def alphaFunction(x, A=1.0, tau=1.0, downAccel=1.0):
    aa= sc.int32(x>0)
    xovertau = x/tau
    return A* xovertau * sc.exp( downAccel*(1 - xovertau))

def trainAlpha(samplingTimes, pulseTimes, tauTrain=1.0,downAccel=1.0):
    """
    train= trainGauss(samplingTimes, pulseTimes,bellSpread=1.0)
    """
    nPts= len(samplingTimes)
    train = sc.zeros(nPts)
    alpha=alphaFunction(samplingTimes,A=1.0,tau=tauTrain,downAccel=downAccel)
    for n in range(len(pulseTimes)):
        nn=gr.find(samplingTimes<pulseTimes[n]).max()
        train[nn:] = train[nn:] + alpha[0: nPts-nn]
        print(train)
    return train


# 
def stimTrains(pars):
    #print 'Obtaining presynaptic spike times and stimulus train'
    sampleTimes=sc.arange(pars['timeMin'],pars['timeMax'],pars['timeStep'])
    pars['stimPeriod']=1000/pars['stimHz']
    preAPs=sc.arange(pars['stimStart'], pars['timeMax'], 1000.0/pars['stimHz'])
    #alphaTrainP=trainAlpha(samplingTimes=sampleTimes, pulseTimes=preAPs[1:], tauTrain=pars['tauTrain'],downAccel=1.0)
    alphaTrainP=trainAlpha(samplingTimes=sampleTimes, pulseTimes=preAPs, tauTrain=pars['tauTrain'],downAccel=1.0)
    alphaTrainX=trainAlpha(samplingTimes=sampleTimes, pulseTimes=preAPs, tauTrain=pars['tauTrain'],downAccel=1.0)
    alphaTrainP= alphaTrainP/alphaTrainP.max()
    alphaTrainX= alphaTrainX/alphaTrainX.max()
    pars['alphaTrainP']= alphaTrainP
    pars['alphaTrainX']= alphaTrainX
    pars['spikesCa']=lambda t: sc.interp(t,sampleTimes, alphaTrainP)
    pars['spikesX']=lambda t: sc.interp(t,sampleTimes, alphaTrainX)
    nStim= len(preAPs)
    peakInds= sc.zeros(nStim,'int32')
    for nn in range(0,nStim):
        peakInds[nn] = 1+gr.find(sampleTimes< preAPs[nn]+pars['tauTrain']).max()
    pars['sampleTimes']=sampleTimes
    pars['preAPs']=preAPs
    pars['peakInds']=peakInds
    pars['nStim']= nStim
    
    return pars

    stimuliTrain=trainAlpha(sampleTimes, preAPs, tauTrain=1.0,downAccel=1.0)

# 
def pRelease(p,t,pa):
    spikeP = pa['spikesCa'](t)
    dp = (p**pa['kP']) * ( pa['asynP']-p)/pa['tauP'] + spikeP * pa['jumpP'] * (1-p)
    return dp

def rrsOccupation(x,t,pa):
    spikeX = pa['spikesX'](t)
    dx = (x**pa['kX']) * ( pa['asynX']-x)/pa['tauX'] - spikeX * pa['asynP'] * x
    return dp


def subeBaja(x,a,b,t1,t2,c):
    e1= sc.exp(-x/t1)
    e2= sc.exp(-x/t2)
    sube= a- e1
    baja= e2 +b 
    return sube*baja+c
# 
def stFD(U,t,pa):
    x,p,dxp=U
    spikeX = pa['spikesX'](t)
    spikeP = pa['spikesCa'](t)
    dx = (x**pa['kX']) * ( pa['asynX']-x)/pa['tauX'] - spikeX * x * p
    dp = (p**pa['kP']) * ( pa['asynP']-p)/pa['tauP'] + spikeP * pa['jumpP'] * (1-p)
    dxp= p*dx + x*dp
    #if  (spike): 
    #    print t, (1-p), pa['jumpP'], (1-p)* pa['jumpP'] 
    return dx, dp, dxp

def simulateFD(pa):
    # Done setting up the stimulus
    simulation=pa
    U0=[pa['asynX'], pa['asynP'], pa['asynX']*pa['asynP']]
    tCrit=pa['preAPs']
    orbit= sc.integrate.odeint(stFD,U0,pa['sampleTimes'],args=(pa,), tcrit=tCrit).transpose()
    simulation['xOrbit']=orbit[0]; 
    simulation['pOrbit']=orbit[1]; 
    simulation['xpOrbit']=orbit[2]
    # Find indices from the time series that correspond to the times right before the pulses
    nPulses=len(tCrit)
    xpPeakInds=sc.zeros(nPulses)
    xpPeaks=sc.zeros(nPulses)
    for n in range(nPulses):
        xpPeakInds[n]=gr.find(pa['sampleTimes']<tCrit[n]).max()
        xpPeaks[n]=orbit[2][xpPeakInds[n]]
    
    simulation['xpNorm']=xpPeaks/xpPeaks[0]
    simulation['figStr1']=r'$\tau_x$=%.1f, $\tau_p$=%.1f, $k_x$=%.1f, $k_p$=%.1f, $h$=%.2f, $x_{\infty}$=%.2f, $p_{\infty}$=%.2f'%(pa['tauX'], pa['tauP'], pa['kX'], pa['kP'], pa['jumpP'], pa['asynX'], pa['asynP'])
    simulation['figName']='taux=%.1f_taup=%.1f_kx=%.1f_kp=%.1f_h=%.2f_xa=%.2f_pa=%.2f_maxT=%d'%(pa['tauX'], pa['tauP'], pa['kX'], pa['kP'], pa['jumpP'], pa['asynX'], pa['asynP'],pa['timeMax'])
    return simulation


def graphSimulation(ax, simData, legend=1):
    #gr.ioff()
    pOrbit=simData['pOrbit']
    xOrbit=simData['xOrbit']
    xpOrbit=simData['xpOrbit']
    xpNorm=simData['xpNorm']
    peakInds=simData['peakInds']
    ax.plot(simData['preAPs'], 1.1*sc.ones(len(simData['preAPs'])), 'k|', ms=10, lw=2, label=r'$t_1,...,t_n$')
    ax.plot(simData['sampleTimes'], xOrbit, 'b:', lw=1, alpha=0.99, label=r'$(t,x)$')
    ax.plot(simData['sampleTimes'], pOrbit, 'k--', lw=1, alpha=0.5, label=r'$(t,p)$')
    ax.plot(simData['sampleTimes'], xpOrbit, 'k', lw=2, alpha=0.5,  label=r'$(t,xp)$')
    ax.plot([simData['sampleTimes'][peakInds[0]],], [xpNorm[0],], 'ro', ms=3, alpha=0.99)
    ax.plot([0,simData['timeMax']], sc.ones(2), 'r', lw=1, alpha=1)#, label=r'$t_1,...,t_n$')
    ax.plot( simData['sampleTimes'][peakInds], xpNorm, 'b', lw=2, alpha=0.8)
    ax.plot( simData['sampleTimes'][peakInds], xpNorm, 'wo', ms=5, alpha=1,  label=r'$(t, xp(t))/xp_1$')
    #ax.set_ylim(0.9,sc.maximum(1.5,1.5*xpNorm.max()))
    ax.set_ylim(0,5,1)
    ax.set_xlim(simData['timeMin'],simData['timeMax'])
    ax.set_xlabel('time (ms)')
    ax.set_title(simData['figStr1'])
    if legend:
        ax.legend(loc='upper center',ncol=5,fontsize=10)
    #gr.ion(); gr.draw()
    return 


def ajusteParametros(simData, expeData, saveFig=1): 
    r=1; c=1
    f0=gr.figure(figsize=(10,5))
    x=sc.arange(0,450,1)
    ax1=f0.add_subplot(r,c,1)
    graphSimulation(ax=ax1, simData=simData, legend=0)
    fitTime=sc.arange(0,pars1['timeMax'],1)
    ax1.plot(fitTime, expeData, 'ko', ms=2)
    ax1.plot(fitTime, expeData, 'k', ms=2, lw=1)
    #ax1.plot(x, dataVals, 'ko', ms=2)
    #ax1.plot(x, dataVals, 'k', lw=1)
    gr.ion()
    #ax1.set_ylim(-0.1,1.1*simData['xpNorm'].max())
    ax1.set_ylim(0,5,1)
    #if saveFig:
        #saveName ='C:\Users\Janet Barroso\Desktop\Work\Modelo\BothEqLogistic\' + simData['figName']+'.eps'
        #f0.savefig(saveName)
        #Dict={'xOrbit':simData['xOrbit'],'pOrbit':simData['pOrbit'],'xpOrbit':simData['xpOrbit'],'xpNorm':simData['xpNorm']}
        #sio.savemat('C:\Users\Janet Barroso\Desktop\Work\Modelo\BothEqLogistic\\'+simData['figName']+'.mat',{'xpOrbit':simData['xpOrbit']})
        #sio.savemat('C:\Users\Janet Barroso\Desktop\Work\Modelo\BothEqLogistic\\'+simData['figName']+'.mat',Dict)
        #sio.savemat('C:\Users\Janet Barroso\Desktop\Work\Modelo\BothEqLogistic\\'+simData['figName']+'.mat',{'xOrbit':simData['xOrbit']},{'pOrbit':simData['pOrbit']})
        #sio.savemat('C:\Users\Janet Barroso\Desktop\Work\Modelo\BothEqLogistic\\'+simData['figName']+'.mat',{'pOrbit':simData['pOrbit']})
    return f0

     
# .................................................................
# Ajuste de parametros
# .................................................................
if 1:
    pars1={'timeMin':0.0, 'timeMax': 500.0, 'timeStep':1e-3,
           'tauX':10.0,  'tauP':1000.0, 
           'asynX':4.0, 'asynP':0.3, 'asynXPm':'ko',
           'kP':1.0, 'kX':1.0, 
           'jumpP':0.07, 'tauTrain':1.0, 
           'stimHz':20.0, 'stimStart':10.0}
    pars1= stimTrains(pars1)
    sim1=simulateFD(pars1)
    #x=sc.arange(0,450,1)
    #dataVals = subeBaja(x=sc.arange(1,sim1['nStim']+1), a=2.1348, b=3.109, t1=1.6353, t2=1.8831, y0=0.3986) #Bi Control
    #dataVals = subeBaja(x=sc.arange(1,sim1['nStim']+1), a=0.8036, b=1.36408, t1=0.001, t2=1.6197, y0=0.4968) #STD control 
    #dataVals = subeBaja(x=sc.arange(1,sim1['nStim']+1), a=1.333, b=1.02, t1=2.153, t2=0.001, y0=1.388) #STF control
    #dataVals = subeBaja(x=sc.arange(1,sim1['nStim']+1), a=0.1672, b=6.76, t1=0.1969, t2=5.163, y0=2.427) #Bi Lesion
    #dataVals = subeBaja(x=sc.arange(1,sim1['nStim']+1), a=0.808, b=1.39, t1=0.001, t2=1.564, y0=0.4937) #STD Lesion
    #dataVals = subeBaja(x=sc.arange(1,sim1['nStim']+1), a=1.887, b=1.736, t1=8.492, t2=0.001, y0=2.51) #STF Lesion
    fitTime=sc.arange(0,pars1['timeMax'],1)
    dataVals = subeBaja(x=fitTime, a=3.09, b=4.7, t1=158.2, t2=37.7, c=-18) #STF Lesion  
    f0= ajusteParametros(simData=sim1, expeData=dataVals, saveFig=0)
    #plt.plot((x,dataVals,'r'))
    plt.show()
