"""
Main astro py MSL program; oneb1 team.
Experimental idea is to spot differences in subsequent photos shortly spaced in time.
The program gets magnetic field data, photos.
Some data about apparent position of the sun and direction with respect to N is computed and recorded.
In case of darkness, photos are not deleted, they are overwritten instead.
One loop every 25 seconds or so.
"""

from sense_hat import SenseHat
from pathlib import Path
from datetime import datetime, timedelta
from time import sleep
import csv
from logzero import logger, logfile
from orbit import ISS
from skyfield.api import load, wgs84
from picamera import PiCamera
import PIL.ExifTags
import PIL.Image


# Variable definitions and settings
earth_nightime="Null"# A silly value initialization

i=1 # For loop numbering purpose
pic=1 # For photo numbering purpose
short_delay=0.06
long_delay=25

# Function definitions

def sun_position(la, lon):
    """ This function computes altitude and azimuth of the sun; it's for guessing at reflection geometric conditions from sea surface"""

    ts = load.timescale()
    t = ts.now()
    planets = load('de440s.bsp')
    earth, sun = planets['earth'], planets['sun']
    ground_point = earth + wgs84.latlon(la,lon)
    astrometric = ground_point.at(t).observe(sun)
    alt, az, d = astrometric.apparent().altaz()
    return alt, az


def chck4night(num):
    """ If brightness values of actual and last photos are less than 0.09, say it's night on earth, else day or twilight;
    the function returns a boolean"""
    
    foto_prec = PIL.Image.open(f"{base_folder}/image_{num-1:04d}.jpg")
    exif_prec = {
                PIL.ExifTags.TAGS[k]: v
                for k, v in foto_prec._getexif().items()
                if k in PIL.ExifTags.TAGS
                }
            
    foto_now = PIL.Image.open(f"{base_folder}/image_{num:04d}.jpg")
    exif_actl = {
                PIL.ExifTags.TAGS[k]: v
                for k, v in foto_now._getexif().items()
                if k in PIL.ExifTags.TAGS
                }
    
    if (exif_prec["BrightnessValue"]<=0.09 and exif_actl["BrightnessValue"]<=0.09):
        earth_night = True
    else:
        earth_night = False
    return earth_night
        

def create_csv(data_file):
    """ The function makes a csv file for data resulting from experiment; headers are set too"""
    with open(data_file, 'w', buffering=1) as f:
        writer = csv.writer(f)
        header = ("Date/time", "Loop number", "Pic number", "earth_nightime", "Mag field x", "Mag field y","Mag field z", "Latitude", "Longitude", "North direction", "Sun altitude", "Sun azimuth")
        writer.writerow(header)


def add_csv_data(data_file, data):
    """ The function adds a new data line to the csv data file"""
    with open(data_file, 'a', buffering=1) as f:
        writer = csv.writer(f)
        writer.writerow(data)
        

def convert(angle):
    """
    Convert a `skyfield` Angle to an EXIF-appropriate
    representation (rationals)
    e.g. 98° 34' 58.7 to "98/1,34/1,587/10"
    Return a tuple containing a boolean and the converted angle,
    with the boolean indicating if the angle is negative.
    """
    sign, degrees, minutes, seconds = angle.signed_dms()
    exif_angle = f'{degrees:.0f}/1,{minutes:.0f}/1,{seconds*10:.0f}/10'
    return sign < 0, exif_angle

def capture(camera, im):
    """Use `camera` to capture an `image` file with lat/long EXIF data."""
    point = ISS.coordinates()

    # Convert the latitude and longitude to EXIF-appropriate representations
    south, exif_latitude = convert(point.latitude)
    west, exif_longitude = convert(point.longitude)

    # Set the EXIF tags specifying the current location
    camera.exif_tags['GPS.GPSLatitude'] = exif_latitude
    camera.exif_tags['GPS.GPSLatitudeRef'] = "S" if south else "N"
    camera.exif_tags['GPS.GPSLongitude'] = exif_longitude
    camera.exif_tags['GPS.GPSLongitudeRef'] = "W" if west else "E"

    # Capture the image
    camera.capture(im)


def doing_stuff(b):
    """ This function does all the main work: it saves one data row and a photo; b is a boolean about shadowing condition of Earth."""
    global i, pic, wavy_clouds_in_photo
    try:
        logger.info(f"Loop number {i} started")
        location = ISS.coordinates()
        lat = location.latitude.degrees
        long = location.longitude.degrees
        logger.info("Loop {} coordinates computed".format(i))

       
        mag_value = sense.get_compass_raw()
        sleep(0.02)
       
        logger.info("Loop {} mag values measured".format(i))
        north_direction = round(sense.get_compass(),3)
        sleep(0.02)
        logger.info("Loop {} N direction measured and rounded to 0.001".format(i))
        for el in mag_value:
            mag_value[el]=round(mag_value[el],3)

       
        logger.info("Loop {} mag values rounded to 0.001".format(i))
        sun_altitude, sun_azimuth = sun_position(lat,long)
        logger.info("Loop {} sun alt-az coordinates computed".format(i))
       
        
        logger.info("Loop {}. Photo number {} checked for wavy clouds".format(i,pic-1))
        row = (datetime.now(), i, pic, b, mag_value["x"], mag_value["y"], mag_value["z"], lat, long, north_direction, sun_altitude, sun_azimuth)# Add entries if needed
        add_csv_data(data_file, row)
        logger.info("Loop {} data line added to csv file".format(i))
        photo = f"{base_folder}/image_{pic:04d}.jpg"
        capture(camera,photo)
        #maybe it would be better to move photo capture call before doing ML check,
        #in this way we might have coral hardware work on current photo (see that 'pic-1' a few lines above)
        logger.info("Loop {} photo saved with photo number {}".format(i,pic))
        pic +=1
        if pic%3==0:
            sleep(short_delay)
        else:
            sleep(long_delay)# reduce sleep time to get more photos
    except Exception as e:
        logger.error(f'{e.__class__.__name__}: {e})')


# Object name definitions
sense = SenseHat()
camera = PiCamera()

# Program main setup stuff

base_folder = Path(__file__).parent.resolve()
data_file = base_folder/'data.csv'
logfile(base_folder/"events.log")
create_csv(data_file)
ephemeris = load('de440s.bsp')
timescale = load.timescale()
camera.resolution=camera.MAX_RESOLUTION# Give this instruction a try
#camera.resolution=(2592,1944)#use this instruction with old version V2 camera
camera.framerate = 15


# Part of program to repeat in a loop over 3 hours of execution

# Create a `datetime` variable to store the start time
start_time = datetime.now()
# Create a `datetime` variable to store the current time
# (these will be almost the same at the start)
now_time = datetime.now()
# Run a loop for 2 minutes

while (now_time < start_time + timedelta(minutes=176)):# properly edit timedelta value
    
    # Camera warm-up time
    if i==1:
        sleep(2)
    doing_stuff(earth_nightime )#earth_nightime value is needed because it must be added to the csv data file
    #sleep(1)
    
    # Update the current time
    now_time = datetime.now()
    i +=1
    # The next two conditionals check for darkness and, if so, the last dark picture is overwritten
    if pic >=3:
        earth_nightime = chck4night(pic-1)
        if earth_nightime:
            pic -= 1

camera.close()
logger.info("Program finished")
