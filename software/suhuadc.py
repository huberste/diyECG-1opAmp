"""
The core SuhuAD class for continuously monitoring A/D Values

The Ear class is the primary method used to access microphone data.
It has extra routines to audomatically detec/test sound card, channel,
and rate combinations to maximize likelyhood of finding one that
works on your system (all without requiring user input!)

Although this was designed to be a package, it's easy enough to work
as an entirely standalone python script. Just drop this .py file in
your project and import it by its filename. Done!
"""

#import pyaudio
import MCP3008
import time
import numpy as np
import threading
import scipy.io.wavfile

def FFT(data,rate):
    """given some data points and a rate, return [freq,power]"""
    data=data*np.hamming(len(data))
    fft=np.fft.fft(data)
    fft=10*np.log10(np.abs(fft))
    freq=np.fft.fftfreq(len(fft),1/rate)
    return freq[:int(len(freq)/2)],fft[:int(len(fft)/2)]

class Adc(object):
    def __init__(self, rate=4096, chunk=128, maxMemorySec=5):
        """
        Prime the ADC to access data. Recording won't start
        until stream_start() is called.
        """

        # configuration
        self.chunk = chunk # doesn't have to be a power of 2
        self.maxMemorySec = maxMemorySec # delete if more than this around
        self.rate=rate
        self.sleeptime = 1.0 / rate

        # internal variables
        self.chunksRecorded=0
        self.mcp = MCP3008.MCP3008() #keep this forever
        self.t=False #later will become threads

    ### SETUP AND SHUTDOWN

    def initiate(self):
        """
        run this after changing settings (like rate) before recording.
        mostly just ensures the sound card settings are good.
        """
        self.msg='recording from '
        self.msg+='MCP3008 channel 1 '
        self.msg+='at %d Hz' % self.rate
        self.data=np.array([])
        print(self.msg)


    def close(self):
        """gently detach from things."""
        print(" -- sending stream termination command...")
        self.keepRecording=False #the threads should self-close
        if self.t:
            while(self.t.isAlive()):
                time.sleep(.1) #wait for all threads to close

    ### LIVE DATA STREAM HANDLING

    def stream_readchunk(self):
        """reads chunks of data until keepRecording is set to False"""
        while self.keepRecording:
            try:
                valuesRead = 0
                values = []
                while valuesRead < self.chunk:
                    t1,timeTook=time.time(),0
                    # the value we get is grounded, so we subtract 512 to supply negative numbers
                    value = self.mcp.read(channel=0) - 512
                    values.append(value)
                    valuesRead += 1
                    timeTook=(time.time()-t1)
#                    print("Reading one value took %.02f ms"%(timeTook*1000))
#                    print("sleeping %.02f ms"%((self.sleeptime - timeTook)*1000))
                    if self.sleeptime - timeTook < 0:
                        print(" -- your device is too slow! Please choose a slower rate!")
                    else:
                        # to get the "rate" right, we need to sleep.
                        time.sleep(self.sleeptime - timeTook)
                data = np.fromiter(values,dtype=np.int16)
                self.data=np.concatenate((self.data,data))
                self.dataFirstI=self.chunksRecorded*self.chunk-len(self.data)
                if len(self.data)>self.maxMemorySec*self.rate:
                    pDump=len(self.data)-self.maxMemorySec*self.rate
#                    print(" -- too much data in memory! dumping %d points."%pDump)
                    self.data=self.data[pDump:]
                    self.dataFirstI+=pDump
            except Exception as E:
                print(" -- exception! terminating...")
                print(E,"\n"*5)
                self.keepRecording=False
        print(" -- stream STOPPED")

    def stream_start(self):
        """adds data to self.data until termination signal"""
        self.initiate()
        print(" -- starting stream")
        self.keepRecording=True # set this to False later to terminate stream
        self.dataFiltered=None
        self.t=threading.Thread(target=self.stream_readchunk)
        self.t.start()

    def stream_stop(self,waitForIt=True):
        """send the termination command and (optionally) hang till its done"""
        self.keepRecording=False
        if waitForIt==False:
            return
        while self.keepRecording is False:
            time.sleep(.1)

    ### WAV FILE AUDIO

    def loadWAV(self,fname):
        """Add audio into the buffer (self.data) from a WAV file"""
        self.rate,self.data=scipy.io.wavfile.read(fname)
        print("loaded %.02f sec of data (rate=%dHz)"%(len(self.data)/self.rate,
                                                     self.rate))
        self.initiate()
        return

    ### DATA RETRIEVAL
    def getPCMandFFT(self):
        """returns [data,fft,sec,hz] from current memory buffer."""
        if not len(self.data):
            return
        data=np.array(self.data) # make a copy in case processing is slow
        sec=np.arange(len(data))/self.rate
        hz,fft=FFT(data,self.rate)
        return data,fft,sec,hz

    def softEdges(self,data,fracEdge=.05):
        """multiple edges by a ramp of a certain percentage."""
        rampSize=int(len(data)*fracEdge)
        mult = np.ones(len(data))
        window=np.hanning(rampSize*2)
        mult[:rampSize]=window[:rampSize]
        mult[-rampSize:]=window[-rampSize:]
        return data*mult

    def getFiltered(self,freqHighCutoff=50):
        if freqHighCutoff<=0:
            return self.data
        fft=np.fft.fft(self.softEdges(self.data)) #todo: filter needed?
        trim=len(fft)/self.rate*freqHighCutoff
        fft[int(trim):-int(trim)]=0
        return np.real(np.fft.ifft(fft))


if __name__=="__main__":
    print("This script is intended to be imported, not run directly!")
