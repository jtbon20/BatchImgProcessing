# import the necessary packages
import argparse
import cv2
import math
import numpy as np
from imutils import paths
import copy




#information for scaling output to a page
pageDim = []
offsets = []
axesScalars = []
printedImg_dict = {}
def initializePage():
    global pageDim, offsets, axesScalars
    #iterate over aspect of a page of paper
    #that will hold the cropped pictures for
    #efficient printing
    #example
    #8"x11" > 20.32cm x 27.94cm > 4images x 5 images
    #(x,y)...(0,3)
    #.
    #.
    #.
    #(4,0)...(4,3)
    dpi = 300
    dimensionsIn = [8.5,11] #inches
    sizeOutputCircles = 1.97 #inches

    numberPerAxes = [int(x / sizeOutputCircles) for x in dimensionsIn]
    offsets = [dpi*(x / sizeOutputCircles - int(x / sizeOutputCircles))/2 for x in dimensionsIn] #pixels

    diam = sizeOutputCircles*dpi #pixels per diameter of picture
    axesScalars = [diam, diam]

    pageDim = [int(x *dpi) for x in dimensionsIn] #pixels

    #initialize dictionary for mapping images in order
    for x in range(0,numberPerAxes[0] + 1):
        for y in range(0,numberPerAxes[1] + 1):
            printedImg_dict[x*numberPerAxes[0]+ y] = (x,y)


#scales image proprotionally using a given height
def resize_image(image, newWidth):
    height,width,depth = image.shape

    size = (newWidth,int(newWidth*(height)/width))
    return cv2.resize(image,size)

# initialize the list of reference points for storing locations of the circle
circleLoc = []
points = []

#calculates center, radius of circle from 2 points on circle
def points_to_circle(p1,p2):

    #coordinates of center
    xC = (p1[0] + p2[0])/2
    yC = (p1[1] + p2[1])/2

    #radius
    r = math.sqrt((xC-p1[0])**2+(yC - p1[1])**2)

    return np.array([int(xC),int(yC),int(r)])

#collects mouse events and processes locations to
def circle_crop_callback(event, x, y, flags, param):
    global circleLoc, points


	# record the starting (x, y) coordinates
    if event == cv2.EVENT_LBUTTONDOWN:
        points = [(x, y)]

	# check to see if the left mouse button was released
    elif event == cv2.EVENT_LBUTTONUP:
		# record the ending (x, y) coordinates and indicate that
		# the cropping operation is finished
        points.append((x, y))

        circleLoc = points_to_circle(points[0], points[1])




def circle_crop(baseTitle, image, clone):
    windowName = str(baseTitle) + "precrop"
    #set up window, mouse callback for cropping
    cv2.namedWindow(windowName, cv2.WINDOW_NORMAL)
    cv2.setMouseCallback(windowName, circle_crop_callback)

    #loops until image cropped to user satisfaction
    while (True):
        if (len(circleLoc)==3): #draw a circle on the image if possible
            cv2.circle(image, (circleLoc[0],circleLoc[1]), circleLoc[2], (0,255,0))

        #display image, wait for user input
        cv2.imshow(windowName, image)
        key = cv2.waitKey(1) #& 0xFF

        # d = decline crop, reset image to try again
        if key == ord("d"):
            image= copy.copy(clone)

	# a = accept crop, process image now
        elif key == ord("a"):
            cv2.destroyAllWindows()

            #mask image with black to crop into circle (from the clone, the non-marked up circle)
            height,width= image.shape[:2]
            circle_mask = np.zeros((height,width), np.uint8)
            cv2.circle(circle_mask,(circleLoc[0],circleLoc[1]), circleLoc[2], 255, thickness=-1)

            return cv2.bitwise_and(clone, clone, mask=circle_mask)

def circle_to_outerbox():
    #x range = x_center - radius > x_center + radius, y is the same
    xRange = (circleLoc[0]-circleLoc[2],circleLoc[0]+circleLoc[2])

    yRange = (circleLoc[1]-circleLoc[2],circleLoc[1]+circleLoc[2])

    return (yRange,xRange)


#because callbacks required for scalar slide events
def hold(x):
    pass

def tune_image(baseTitle, image, clone):
    #create scalars
    colorScalars = [1,1,1]
    colorScaleMax = 100

    #initialize window, and trackbars to tune channel params
    windowName = str(baseTitle) + "pretune"
    cv2.namedWindow( windowName)
    cv2.createTrackbar('R', windowName,colorScaleMax,colorScaleMax, hold)
    cv2.createTrackbar('G', windowName,colorScaleMax,colorScaleMax, hold)
    cv2.createTrackbar('B', windowName,colorScaleMax,colorScaleMax, hold)



    while(True):
        # get current positions of modifier trackbars and update image
        colorScalars[0]= cv2.getTrackbarPos('R',windowName)/colorScaleMax
        colorScalars[1]= cv2.getTrackbarPos('G',windowName)/colorScaleMax
        colorScalars[2]= cv2.getTrackbarPos('B',windowName)/colorScaleMax
        #so that color information can be regained from sliders
        temp = copy.copy(image)
        for i in range(0,3):
            temp[:,:,i] = image[:,:,i] * colorScalars[i]

        #display new picture in greyscale, wait for user keypress
        grey = cv2.cvtColor(temp, cv2.COLOR_BGR2GRAY)
        cv2.imshow(windowName, grey)
        key = cv2.waitKey(1)

        #deny changes >> resets image to clone
        if key == ord("d"):
            image= copy.copy(clone)

        #accept changes >> saves image
        elif key == ord("a"):
            cv2.destroyAllWindows()
            return grey

def finalize_image(image):
    height,width= image.shape[:2]
     #create mask based on user-approved circle
    circle_mask = np.zeros((height,width), np.uint8)
    cv2.circle(circle_mask,(circleLoc[0],circleLoc[1]), circleLoc[2],255,thickness=-1)

    #foreground
    fg = cv2.bitwise_or(image, image, mask=circle_mask)

    #background = inverted mask on white background
    invMask = cv2.bitwise_not(circle_mask)
    background = np.full(image.shape, 255, dtype=np.uint8)
    bg = cv2.bitwise_or(background, background, mask=invMask)
    #final = clipped foreground + inverse clipped background
    whitebgimg = cv2.bitwise_or(fg, bg)

    #crop image to square around circle
    cropRange = circle_to_outerbox()

    return whitebgimg[cropRange[0][0]:cropRange[0][1], cropRange[1][0]:cropRange[1][1]]


def arrange_images():
    #initialize blank image to drop pictures onto
    #onto pages in batches of 20
    printedSheet = np.full((pageDim[0],pageDim[0],3),255, dtype=np.uint8)

    count = 0
    for finalizedImage in paths.list_images(args.output):
        #get x,y locations on page
        x,y = printedImg_dict[count]
        count+=1
        print(str(finalizedImage))
        #open image & resize to print size
        scaledImage = resize_image(cv2.imread(finalizedImage,1), int(axesScalars[0]))

        y_base = int(offsets[1] + y*axesScalars[1])
        x_base = int(offsets[0] + x*axesScalars[0])

        printedSheet[y_base:y_base+scaledImage.shape[0], x_base:x_base+scaledImage.shape[1]] = scaledImage

    #save image
    cv2.imwrite( ""+args.output + "printsheet.PNG", printedSheet)


# construct the argument parse and parse the arguments
parser = argparse.ArgumentParser(description='''This script allows the batch processing of images to make into circular gray-scale images ready to be printed on ornaments.''')
parser.add_argument("-i", "--images", required=True, help="base path to input directory of images")
parser.add_argument("-o", "--output", required=True, help="base path to output directory of images")
args = parser.parse_args()


initializePage()

#declarations
count = 0

#iterate over images to process
for imagePath in paths.list_images(args.images):
    count+=1

    #open image & resize to fit window
    scaledImage = resize_image(cv2.imread(imagePath,1),500) #reasonable size for computer

    #crop image, create image clone to enable redo's
    croppedImage = circle_crop(count, scaledImage, copy.copy(scaledImage))

    #tune image by tweaking channels, create image clone to enable redo's
    tunedImage = tune_image(count, croppedImage, copy.copy(croppedImage))

    finalizedImage = finalize_image(tunedImage)

    #save image
    cv2.imwrite(""+args.output + str(count) + "batch2final.PNG", finalizedImage)
    cv2.destroyAllWindows()

arrange_images()
