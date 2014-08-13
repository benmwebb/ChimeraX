chain_colors = {
'a':(123,104,238),
'b':(240,128,128),
'c':(143,188,143),
'd':(222,184,135),
'e':(255,127,80),
'f':(128,128,128),
'g':(107,142,35),
'h':(100,100,100),
'i':(255,255,0),
'j':(55,19,112),
'k':(255,255,150),
'l':(202,62,94),
'm':(205,145,63),
'n':(12,75,100),
'o':(255,0,0),
'p':(175,155,50),
'q':(0,0,0),
'r':(37,70,25),
's':(121,33,135),
't':(83,140,208),
'u':(0,154,37),
'v':(178,220,205),
'w':(255,152,213),
'x':(0,0,74),
'y':(175,200,74),
'z':(63,25,12),
'1': (87, 87, 87),
'2': (173, 35, 35),
'3': (42, 75, 215),
'4': (29, 105, 20),
'5': (129, 74, 25),
'6': (129, 38, 192),
'7': (160, 160, 160),
'8': (129, 197, 122),
'9': (157, 175, 255),
'0': (41, 208, 208),
#'A': (255, 146, 51),
#'B': (255, 238, 51),
#'C': (233, 222, 187),
#'D': (255, 205, 243),
}
default_color = (170,170,170)


from random import randint, seed
seed(1)         # Get same colors each time program is run.
from numpy import array, uint8, empty
rgba_256 = array([(randint(80,255), randint(80,255), randint(80,255), 255) for i in range(256)], uint8)
for cid,rgb in chain_colors.items():
    rgba_256[ord(cid),:3] = rgb
    rgba_256[ord(cid.upper()),:3] = rgb

element_rgba_256 = ec = empty((256,4), uint8)
ec[:,:3] = 180
ec[:,3] = 255
ec[6,:] = (255,255,255,255)     # H
ec[6,:] = (144,144,144,255)     # C
ec[7,:] = (48,80,248,255)       # N
ec[8,:] = (255,13,13,255)       # O
ec[15,:] = (255,128,0,255)      # P
ec[16,:] = (255,255,48,255)      # S
