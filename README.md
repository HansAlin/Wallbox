# Wallbox
Wallbox is for anyone that have a GARO wallbox (GLB Fixed cable Wifi) for charging their Nissan Leaf and that have spotprices on electric power from Nordpool.

The code is currently running on a UBUNTU machine. However the goal is to implement the code on a Raspberry Pi. 

## Notes
1. In the code there is a function that reads the temperature from a device on my roof. The reason for that is the power should be available when it is low temperature. If you don't implement temperature reader the function just returns False, it is not low temperature.
2. I had to modifie the the LEAF library in order to make it work.
3. It is possible to use the code even if you don't have a Nissan Leaf just change this part of the code: `hours, soc = leaf_status()`

