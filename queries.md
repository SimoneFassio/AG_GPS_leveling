I want to create a software for leveling terrain using pyQt5.
must have those features:
- receive GPS data from the loopback at port 15555.

-show a real time plot of the field I'm with the color grade that represents the elevation. At startup it is asked if continue an old field or start a new one. if a new one is started the first phase is to collect the GPS points so Is asked to drive through the field and new gps points are plotted in real time. the GPS points must be converted to a local metric system. At the end of the survey phase a button must be pressed to save the field and the second phase start. (if the field was already present when is open start this phase).
also a point must be shown on the plot that represents the current location of the tractor.
-levelling phase: the desired slope along the two axis is asked to the user (in terms of cm/100m) and the target elevation for each point is calculated and plotted whit a color scale going from red to blue: red where the target elevation is under the survey elevation and blue where the target is above the survey. Also on the right of the screen with a colored bar the difference between the survey and the target elevation is shown.
Also add the possibility to automatically compute the best target elevation instead of the user input the slope. the best target elevation is defined as the slope on the two axis that minimize the volume of terrain moved. 

Organize the program into multiple files and classes, it must be very modular and easy to update or implement new features. write ALL the code for ALL the features I asked.

moreover:
1- in the leveling phase interpolate the survey points on a grid and display it as a continuous plot and not as a set of points. also the computation of the target elevation must be done a grid to have equally spaced points.  remember to show as a bar on the right the difference in elevation from the actual received from the GPS and the target.
2- in the levelling phase I want to see my position in the field with a point and must be updated in real time. also, I'm using a working width of 4 meters, I want the survey elevation to be updated on the grid as soon as I cover those points with the new elevation coming from the antenna. 
3- add status indicators on the right part of the application telling if GPS position is being received

Also add near the GPS status a textbox with the current elevation coming from GPS and in the leveling add also the target elevation and the difference between the two.
