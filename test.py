#!/usr/bin/env python
#
# Author: Youngbae Ham (astro422@kopri.re.kr)
#
####@@@@@@@@@@@@@@@@@@@@@@@@@@@@@ WARNNING @@@@@@@@@@@@@@@@@@@@@@@@@@@@@####
## This code is valid only if the time zone of the LINUX system is set to U.K.
## This problem can be solved with 'pytz' module.
####@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@####

####@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@ NOTE @@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@####
# ----------------------- Camera setting limitations ----------------------
# Valid min. value for 'Exposure': 1 [micro sec]
# Valid min. value for 'Interval': 4 [sec]
# Valid min. difference btwn. 'Exposure' & 'Interval': Greater than 2 [sec]
# These limitations could be improved after modifying and testing parameters
# related to these camera setting variables.
# -------------------------------------------------------------------------
#
# The algorithm used to reach the exact target observation time is designed
# to perform efficient WHILE loop repeatation and precise timing. Regardless
# of the length of the exposure time, the algorithm only requires repeatati-
# ons less than 150, and only uses CPU resources less than 1%. In the test
# run, this algorithm guaranteed the timing accuracy with errors less than
# 0.1 milliseconds (More precise accuracy better than 0.1 can be achieved,
# but it requires more resource).
#
# The WHILE loop for controlling exposure is escaped when the status value
# returned by 'ASIGetExpStatus' becomes 2. An error encountered in the test
# observation indicated that the code could not escape this WHILE loop (and
# the reason is suspected that 'ASIGetExpStatus' becomes not to return the
# status value of 2). This error also happened with the prototype code
# 'https://urldefense.com/v3/__http://test_importing_ZWO_SDK.py__;!!DLa72PTfQgg!KQIGbB4motUzBOSFmjW-jnF1LDLYTT7ES0zAXDNfDayGpZU_PoNFC4DtHV6ytVfl_-p84WbxrW2p9k-l1r5p$ '. JBS A-ASC also uses ZWO-ASI, and it looks
# like similar error happens with the Synoptix software. The code is updated
# to handle this error. When it happens, error-log will be written.
#
# 'Exp_tag' variable defines the suffix for the output filename. The suffix
# represents the exposure time used for the image acquisition. 'Exp_tag' is
# Optimized to millisecond exposure, thus setting 'Exposure' variable in
# micro second leads to wrong suffix.
#
# output filename example:
#   /mnt/ASC_DATA/YYYY/MM/DD/KAGO-ASC_YYYYMMDD_hhmmss_??????ms.tif
####@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@####

##########------------------------SETTINGS------------------------##########
#### Site settings
location={'lat':'-72.32','lon':'170.23','elevation':3}
#location={'lat':'37.05','lon':'126.71','elevation':0}
alt_cutoff = -10 #[Degree]
####

#### Observation settings
## Set image binning and cropping
binning=1
cx, cy = 998, 588 # center of the image (depend on the variable 'binning')
c_bin=600 # 1/2 of the crop size (depneds on the variable 'binning')
##
## Set gain, exposure, and observation interval
Gain=0
Exposure=15000000 #[micro second]
Interval=60 # [second] time interval between the each image
Marginal=3 # [second] time for checking the validity of the first target observation time (3 seconds -> relaxed too much? RPI's performance...)
##
## Set the prefix of the output image's filename
device_name='KAGO-ASC3'
##
####
#### Import external libraries
import ctypes as c
import time
import numpy as np
import ephem
from PIL import Image
import os
####
#### Directory settings
user=os.getlogin()
out_paren_dir='/ASC_DATA/'+user+'/' # output file path
log_dir='/home/'+user+'/logs/'
log1=log_dir+'log_ASC_control.log' # logfile that errors are recorded mainly
####
##########--------------------------------------------------------##########

####@@@@@@@@@@@@@@@@@@@ Information for ZWO ASI SDK @@@@@@@@@@@@@@@@@@@@####
# List of ASI_ERROR_CODE
#*  0: ASI_SUCCESS = 0,// operation was successful
#*  1: ASI_ERROR_INVALID_INDEX, //no camera connected or index value out of boundary
#*  2: ASI_ERROR_INVALID_ID, //invalid ID
#*  3: ASI_ERROR_INVALID_CONTROL_TYPE, //invalid control type
#*  4: ASI_ERROR_CAMERA_CLOSED, //camera didn't open
#*  5: ASI_ERROR_CAMERA_REMOVED, //failed to find the camera, maybe the camera has been removed
#*  6: ASI_ERROR_INVALID_PATH, //cannot find the path of the file
#*  7: ASI_ERROR_INVALID_FILEFORMAT,
#   8: ASI_ERROR_INVALID_SIZE, //wrong video format size
#*  9: ASI_ERROR_INVALID_IMGTYPE, //unsupported image format
#  10: ASI_ERROR_OUTOF_BOUNDARY, //the startpos is outside the image boundary
#* 11: ASI_ERROR_TIMEOUT, //timeout
# 12: ASI_ERROR_INVALID_SEQUENCE,//stop capture first
#* 13: ASI_ERROR_BUFFER_TOO_SMALL, //buffer size is not big enough
# 14: ASI_ERROR_VIDEO_MODE_ACTIVE,
#* 15: ASI_ERROR_EXPOSURE_IN_PROGRESS,
#* 16: ASI_ERROR_GENERAL_ERROR,//general error, eg: value is out of valid range
#* 17: ASI_ERROR_END --->>>???

# List of ASI_EXPOSURE_STATUS
# 0: ASI_EXP_IDLE=0,//idle, ready to start exposure
# 1: ASI_EXP_WORKING,//exposure in progress
# 2: ASI_EXP_SUCCESS,//exposure completed successfully, image can be read out
# 3: ASI_EXP_SUCCESS,//exposure failure, need to restart exposure

# List of ASI_IMG_TYPE
# 0: ASI_IMG_RAW8 = 0,// Each pixel is an 8-bit (1 byte) gray level
# 1: ASI_IMG_RGB24,// Each pixel consists of RGB, 3 bytes totally (color cameras only)
# 2: ASI_IMG_RAW16,// 2 bytes for every pixel with 65536 gray levels
# 3: ASI_IMG_Y8,// monochrome mode,1 byte every pixel (color cameras only)
# 4: ASI_IMG_END = -1

# available ASI_IMG_TYPE for ZWO ASI-178MM
# 0: ASI_IMG_RAW8
# 2: ASI_IMG_RAW16
# Refer to camInfo.SupportedVideoFormat
####@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@####


Initial_sleep_time=0 # Sleep time for the safety preventing unstopable reboot (It can be omitted in the final version in the future)
print('Start ASC control code - Waiting '+str(Initial_sleep_time)+' sec')
os.system('echo "'+'$(date +"%F %T %Z")'+'" [INITIAL] Start ASC control code - Waiting '+str(Initial_sleep_time)+' seconds >> '+log1)
time.sleep(Initial_sleep_time)


## Set image type of the output images
## -- For ASI_IMG_RAW16
imgType=2 # ASI_IMG_RAW16
buffType=np.uint16
buffMult=2
buffMode='I;16'
##--
##
##-- For ASI_IMG_RAW8
# imgType=0
# buffType='U2'
# buffMult=1
# buffMode='L'
##

## Prepare classes for ZWO ASI SDK through ctypes library
class ASI_CAMERA_INFO(c.Structure):
    _fields_ = [
        ('Name', c.c_char * 64),
        ('CameraID', c.c_int),
        ('MaxHeight', c.c_long),
        ('MaxWidth', c.c_long),
        ('IsColorCam', c.c_int),
        ('BayerPattern', c.c_int),
        ('SupportedBins', c.c_int * 16),
        ('SupportedVideoFormat', c.c_int * 8),
        ('PixelSize', c.c_double),  # in um
        ('MechanicalShutter', c.c_int),
        ('ST4Port', c.c_int),
        ('IsCoolerCam', c.c_int),
        ('IsUSB3Host', c.c_int),
        ('IsUSB3Camera', c.c_int),
        ('ElecPerADU', c.c_float),
        ('BitDepth', c.c_int),
        ('IsTriggerCam', c.c_int),

        ('Unused', c.c_char * 16)
    ]

class ASI_CONTROL_CAPS(c.Structure):
    _fields_ = [
        ('Name', c.c_char * 64),
        ('Description', c.c_char * 128),
        ('MaxValue', c.c_long),
        ('MinValue', c.c_long),
        ('DefaultValue', c.c_long),
        ('IsAutoSupported', c.c_int),
        ('IsWritable', c.c_int),
        ('ControlType', c.c_int),
        ('Unused', c.c_char * 32),
        ]
##

## Prepare body for ephem module
site=ephem.Observer()
site.lat=location['lat']
site.lon=location['lon']
#site.elevation=location['elevation']
##

## Load the shared library into c types
asi=c.CDLL("/home/"+user+"/asi_env/lib/python3.7/asi_project/ZWO_SDK/http://libASICamera2.so__;!!DLa72PTfQgg!KQIGbB4motUzBOSFmjW-jnF1LDLYTT7ES0zAXDNfDayGpZU_PoNFC4DtHV6ytVfl_-p84WbxrW2p9hlC-4pI$ ")
##

numCam=asi.ASIGetNumOfConnectedCameras()
print('## Number of Connected ZWO Cameras: {0}'.format(numCam)) # Get the number of the connected cameras

## Handles the number of cameras detected
if numCam==0:
    print('## -> No camera detected')
    print('Need to reboot?')
    os.system('echo "'+'$(date +"%F %T %Z")'+'" [ ERROR ] Checking camera - No camera detected [Start rebooting] >> '+log1)
    os.system('sudo reboot')
elif numCam==1:
    print('## -> 1 camera detected')
    os.system('echo "'+'$(date +"%F %T %Z")'+'" [INITIAL] Checking camera - 1 camera detected [Start observation] >> '+log1)
else:
    print('## -> Multiple cameras detected')
    print('What will you do?')
##

#camInfo=ct.c_int()

camIdx=0 # Set camera index number

## Get camera's information
camInfo=ASI_CAMERA_INFO()
stat=asi.ASIGetCameraProperty(c.byref(camInfo), camIdx)
print('... Get camera info (status={0})'.format(stat))
##

## Set Dimensions of the output images based on the binning setting
imgWidth=int(camInfo.MaxWidth/binning)
imgHeight=int(camInfo.MaxHeight/binning)
##

## set variables related to the exposure time
Exp_tag='_'+(str(Exposure//1000)).zfill(6)+'ms' # suffix of the output filename (exposure time in ms)
Num_exp_check_step=10 # the number of the while loop for exposure cannot exceed this number
Exp_check_step=Exposure/1000000/Num_exp_check_step # [second] time interval for checking the exposure status
##the number of the while loop for exposure cannot exceed this number
## Num_exp_check_step variable is important because it is related to handle the error of stopping exposure
##
## set final sleep time for checking exposure time
Fin_sleep_time=(Interval-Exposure/1000000)*0.1 # [second]
##

print('## List of Cameras')
print('CamID={0}, CamName:{1}'.format(camInfo.CameraID,str(camInfo.Name)[2:-1]))

# Close camera before openning camera
stat=asi.ASICloseCamera(camInfo.CameraID)
# Open camera
stat=asi.ASIOpenCamera(camInfo.CameraID)
print('... Open camera (status={0})'.format(stat))
if stat!=0:
    os.system('echo "'+'$(date +"%F %T %Z")'+'" [ ERROR ] Cannot open camera [Stat='+str(stat)+'] - Initial camera openning failed [Start rebooting] >> '+log1)
    os.system('sudo reboot')

'''
numCtrl=c.c_int()
stat=asi.ASIGetNumOfControls(camInfo.CameraID, c.byref(numCtrl))
print('... Get number of control (status={0})'.format(stat))

print('## List of Control capability')
ctrlInfo=ASI_CONTROL_CAPS()
for i in range(numCtrl.value):
    stat=asi.ASIGetControlCaps(camInfo.CameraID, i, c.byref(ctrlInfo))
    print(str(https://urldefense.com/v3/__http://ctrlInfo.Name__;!!DLa72PTfQgg!KQIGbB4motUzBOSFmjW-jnF1LDLYTT7ES0zAXDNfDayGpZU_PoNFC4DtHV6ytVfl_-p84WbxrW2p9iN9uYzG$ )[2:-1],': ', str(ctrlInfo.Description)[2:-1])
'''

## Prepare camera
stat=asi.ASIInitCamera(camInfo.CameraID) # Initialize Camera
os.system('echo "'+'$(date +"%F %T %Z")'+'" [INITIAL] Prepare camera - Initialize camera [Stat='+str(stat)+'] >> '+log1)
stat=asi.ASISetROIFormat(camInfo.CameraID, imgWidth, imgHeight, binning, imgType) # Set ROI format
os.system('echo "'+'$(date +"%F %T %Z")'+'" [INITIAL] Prepare camera - Set ROI format [Stat='+str(stat)+'] >> '+log1)
stat=asi.ASISetStartPos(camInfo.CameraID, 0, 0) # Set start position
os.system('echo "'+'$(date +"%F %T %Z")'+'" [INITIAL] Prepare camera - Set start position [Stat='+str(stat)+'] >> '+log1)
stat=asi.ASISetControlValue(camInfo.CameraID, 0, Gain, False) # Set Camera control value (Gain)
os.system('echo "'+'$(date +"%F %T %Z")'+'" [INITIAL] Prepare camera - Set camera gain [Stat='+str(stat)+'] >> '+log1)
stat=asi.ASISetControlValue(camInfo.CameraID, 1, Exposure, False) # Set Camera control value (Exposure time)
os.system('echo "'+'$(date +"%F %T %Z")'+'" [INITIAL] Prepare camera - Set camera exposure [Stat='+str(stat)+'] >> '+log1)
##


## Determine target obs. time - Tricky way (gmtime->mktime->localtime gives the intended result, lol)
Curr_UT=time.gmtime() # Current UT timestamp (tuple)
#Curr_UT_UNIX=time.mktime(Curr_UT) # UNIX time of the current UT
Curr_UT_UNIX=time.time()
UT_MMSS_sec=Curr_UT.tm_min*60 + Curr_UT.tm_sec # Time in seconds calculated with Minute and Second
mod=UT_MMSS_sec % Interval # Time fraction for determining first target obs. time
target_UT_UNIX=Curr_UT_UNIX + (Interval - mod) # UNIX time of the target obs. time
if target_UT_UNIX - Curr_UT_UNIX < Marginal: # Check if the current time is too close to the target obs. time
    target_UT_UNIX+=Interval # Move to the next target time
target_UT_time=time.localtime(target_UT_UNIX) # Convert UNIX time of the target obs. time to UT timestamp (tuple)
##

while True: # This is non-escapable loop
    YYYY=str(target_UT_time.tm_year)
    MM=(str(target_UT_time.tm_mon)).zfill(2)
    DD=(str(target_UT_time.tm_mday)).zfill(2)
    HHMMSS=(str(target_UT_time.tm_hour)).zfill(2)+(str(target_UT_time.tm_min)).zfill(2)+(str(target_UT_time.tm_sec)).zfill(2)
    TIMESTAMP=YYYY+MM+DD+'_'+HHMMSS # Timestamp for output file name
    out_full_dir=out_paren_dir+YYYY+'/'+MM+'/'+DD+'/' # output directory for the image including /YYYY/MM/DD/ subdirectory
    print(TIMESTAMP)
    ## Calculate Sun's information for the current target obs. time
    site.date=(ephem.Date(target_UT_time[0:6]))
    sun=ephem.Sun(site)
    sun_alt=sun.alt*180/np.pi
    ##
    if sun_alt <= alt_cutoff: # Check observation condition
        print("Sun's elevation: GOOD ({0:6.2f} deg)".format(sun_alt))
        wait_time=(target_UT_UNIX - time.time())
        if wait_time > 1:
            time.sleep(wait_time-1)
        wait_time=(target_UT_UNIX - time.time())*0.9
        counter=0
        while True: # While loop for checking whether exact obs. time is reached
            ## This while loop is efficiently working for time less than 1 second (the wait_time is designed to be a geometric series)
            time.sleep(wait_time)
            counter+=1
            Curr_UT_UNIX=time.time()
            if target_UT_UNIX - Curr_UT_UNIX < 0.0001: # Exact obs. time reached (Start exposure)
                ERR1=0 # Flags for ERROR HANDLER 1 (0: Normal, 1: Error)
                print('Iteration: {0}, timing error: {1:15.7f} milliseconds'.format(counter,(target_UT_UNIX-Curr_UT_UNIX)*1000))
#                print('Exact time counter={0}'.format(counter))
                stat=asi.ASIStartExposure(camInfo.CameraID) # Capture image
                print('... Start exposure (status={0})'.format(stat))
                step_counter=0 # To deal with endless exposure error (Check the number of repeatation of the while loop for exposure)
                sleep_time=Exp_check_step
                while True: # while loop for exposure
                    time.sleep(sleep_time) # For saving CPU resource
                    step_counter+=1
                    expStat=c.c_int()
                    stat=asi.ASIGetExpStatus(camInfo.CameraID, c.byref(expStat))
                    if expStat.value == 2: # Stopping exposure succeess. Break while loop for exposure
#                        print(step_counter,expStat.value,sleep_time)
                        break # Breaker for the 3rd WHILE loop (Stopping exposure is done)
#                    print(step_counter,expStat.value,sleep_time)
                    if step_counter == Num_exp_check_step: # Set the final sleep time
#                        print('update sleep time')
                        sleep_time=Fin_sleep_time
                    if step_counter > Num_exp_check_step: ## ERROR HANDLER 1
                        ERR1=1
                        ## step_counter cannot be greater than Num_exp_check_step at this point!
                        ## Invalid settings for 'Exposure' and 'Interval' can lead the code here (BE CAREFUL)
                        ## Otherwise, entrance to this if statement indicates that there is an error in stopping exposure!
                        print('...... Number of steps for checking exposure status: {0}'.format(step_counter))
                        print('...... !Cannot stop exposure')
                        numCam=asi.ASIGetNumOfConnectedCameras() # Check the number of the connected camera
                        if numCam==0:
                            os.system('echo "'+'$(date +"%F %T %Z")'+'" [ ERROR ] Cannot stop exposure [expStat='+str(expStat.value)+'] - No camera detected [Start rebooting] >> '+log1)
                            print('...... Cannot find camera write log for USB devices and reboot')
                            os.system("dmesg -T | grep -i usb > '"+log_dir+"USBstat_'"+'"$(date +"%F_%H%M%S")"'+"'.log'")
                            os.system('sudo reboot')
                        else:
#                            os.system('echo "'+'$(date +"%F %T %Z")'+'" [ ERROR ] Cannot stop exposure [expStat='+str(expStat.value)+'] - Camera detected [Attempt reloading camera] >> '+log1)
                            os.system('echo "'+'$(date +"%F %T %Z")'+'" [ ERROR ] Cannot stop exposure [expStat='+str(expStat.value)+'] - Camera detected [Start rebooting] >> '+log1)
                            os.system('sudo reboot')
                        '''
                        print('...... Reload the camera')
                        ## Prepare the camera again
                        stat=asi.ASICloseCamera(camInfo.CameraID)
                        camInfo=ASI_CAMERA_INFO()
                        stat=asi.ASIGetCameraProperty(c.byref(camInfo),camIdx)
                        stat=asi.ASIOpenCamera(camInfo.CameraID)
                        if stat!=0: # Failed to reload camera
                            os.system('echo "'+'$(date +"%F %T %Z")'+'" [ ERROR ] Cannot open camera [Stat='+str(stat)+'] - Reloading camera failed [Start rebooting] >> '+log1)
                            os.system('sudo reboot')
                        os.system('echo "'+'$(date +"%F %T %Z")'+'" [RECOVER] Reloading camera successed - System back to normal status [Keep going] >> '+log1)
                        stat=asi.ASIInitCamera(camInfo.CameraID)
                        stat=asi.ASISetROIFormat(camInfo.CameraID, imgWidth, imgHeight, binning, imgType)
                        stat=asi.ASISetStartPos(camInfo.CameraID, 0, 0)
                        stat=asi.ASISetControlValue(camInfo.CameraID, 0, Gain, False)
                        stat=asi.ASISetControlValue(camInfo.CameraID, 1, Exposure, False)
                        ##
                        '''
                        print('...... Update the target time')
                        ## Update target obs. time
                        target_UT_UNIX=time.mktime(target_UT_time) + Interval
                        if target_UT_UNIX - time.time() < Marginal:
                            target_UT_UNIX+=Interval
                        target_UT_time=time.localtime(target_UT_UNIX)
                        ##
                        break # Breaker for the 3rd WHILE loop (We must also break 2nd WHILE loop too)
                if ERR1 == 0: # When stopping exposure will success
                    stat=asi.ASIStopExposure(camInfo.CameraID) # stop exposure
                    print('... Stop exposure (status={0})'.format(stat))
#                    print('Number of steps: {0}'.format(step_counter))
                    fb=np.zeros((imgWidth,imgHeight), dtype=buffType) # prepare buffer for acquired image
                    stat=asi.ASIGetDataAfterExp(camInfo.CameraID, fb.ctypes,imgWidth*imgHeight*buffMult)
                    print('... Get image buffer (status={0})'.format(stat))
                    img=Image.frombuffer(buffMode,(imgWidth,imgHeight),fb,'raw',buffMode,0,1) # Get image from Buffer
                    img=img.crop((cx-c_bin,cy-c_bin,cx+c_bin,imgHeight-1)) # Crop image for saving storage
                    os.makedirs(out_full_dir,exist_ok=True) # Make output directory
                    img.save(out_full_dir+device_name+'_'+TIMESTAMP+Exp_tag+'.png') # Save image
                    target_UT_UNIX=time.mktime(target_UT_time) + Interval # prepare UNIX time of the next target obs. time
                    target_UT_time=time.localtime(target_UT_UNIX) # Convert UNIX time of the next target obs. time to UT timestamp (tuple)
                    break # Breaker for the 2nd WHILE loop (Camera control finished for this target obs. time)
                else: # When stopping exposure will fail, but recovered (obsolete since Mar/05/2021)
                    ERR1=0 # reset exposure error status
                    break # Breaker for the 2nd WHILE loop when exposure error happened
            wait_time=wait_time*0.09 # Update sleep time with a common ratio of 0.09
    else: # Just while loop and update target_UT_UNIX and target_UT_time
        print("Sun's elevation: BAD ({0:6.2f} deg)".format(sun_alt))
        wait_time=(target_UT_UNIX - time.time())
        if wait_time >1:
            time.sleep(wait_time-1)
        wait_time=(target_UT_UNIX - time.time())*0.9
        while True:
            time.sleep(wait_time)
            curr_UT_UNIX=time.time()
            if target_UT_UNIX - curr_UT_UNIX < 0.01:
                target_UT_UNIX=time.mktime(target_UT_time) + Interval
                target_UT_time=time.localtime(target_UT_UNIX)
                break
            wait_time=wait_time*0.09 # Update sleep time with a common ratio of 0.09
            
## Close camera (ASICloseCamera) - There'll be no chance of executing this line
stat=asi.ASICloseCamera(camInfo.CameraID)
##