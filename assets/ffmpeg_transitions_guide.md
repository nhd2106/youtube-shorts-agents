ffmpeg -i inputVideo1.mp4 -i inputVideo2.mp4 -filter_complex xfade=transition=radial:duration=5:offset=0 radialVideo.mp4

ffmpeg -i inputVideo1.mp4 -i inputVideo2.mp4 \
-filter_complex xfade=transition=dissolve:duration=3:offset=3 \
dissolveVideo.mp4


ffmpeg -i inputVideo1.mp4 -i inputVideo2.mp4 -filter_complex xfade=transition=circleopen:duration=5:offset=0 circleOpenVideo.mp4

ffmpeg -i inputVideo1.mp4 -i inputVideo2.mp4 -filter_complex xfade=transition=circleclose:duration=5:offset=0 circleCloseVideo.mp4

ffmpeg -i inputVideo1.mp4 -i inputVideo2.mp4 -filter_complex xfade=transition=pixelize:duration=5:offset=0 pixelizeVideo.mp4


ffmpeg -i inputVideo1.mp4 -i inputVideo2.mp4 -filter_complex xfade=transition=hlslice:duration=5:offset=0 hlsliceVideo.mp4


ffmpeg -i inputVideo1.mp4 -i inputVideo2.mp4 -filter_complex xfade=transition=hrslice:duration=5:offset=0 hrsliceVideo.mp4


ffmpeg -i inputVideo1.mp4 -i inputVideo2.mp4 -filter_complex xfade=transition=vuslice:duration=5:offset=0 vusliceVideo.mp4

ffmpeg -i inputVideo1.mp4 -i inputVideo2.mp4 -filter_complex xfade=transition=vdslice:duration=5:offset=0 vdsliceVideo.mp4

ffmpeg -i inputVideo1.mp4 -i inputVideo2.mp4 -filter_complex xfade=transition=hblur:duration=5:offset=0 hblurVideo.mp4

ffmpeg -i inputVideo1.mp4 -i inputVideo2.mp4 -filter_complex xfade=transition=fadegrays:duration=5:offset=0 fadegraysVideo.mp4

ffmpeg -i inputVideo1.mp4 -i inputVideo2.mp4 -filter_complex xfade=transition=fadeblack:duration=5:offset=0 fadeblackVideo.mp4

ffmpeg -i inputVideo1.mp4 -i inputVideo2.mp4 -filter_complex xfade=transition=fadewhite:duration=5:offset=0 fadewhiteVideo.mp4


ffmpeg -i inputVideo1.mp4 -i inputVideo2.mp4 -filter_complex xfade=transition=rectcrop:duration=5:offset=0 rectcropVideo.mp4


ffmpeg -i inputVideo1.mp4 -i inputVideo2.mp4 -filter_complex xfade=transition=circlecrop:duration=5:offset=0 circlecropVideo.mp4


ffmpeg -i inputVideo1.mp4 -i inputVideo2.mp4 -filter_complex xfade=transition=wipeleft:duration=5:offset=0 wipeleftVideo.mp4


ffmpeg -i inputVideo1.mp4 -i inputVideo2.mp4 -filter_complex xfade=transition=wiperight:duration=5:offset=0 wiperightVideo.mp4


ffmpeg -i inputVideo1.mp4 -i inputVideo2.mp4 -filter_complex xfade=transition=slidedown:duration=5:offset=0 slidedownVideo.mp4


ffmpeg -i inputVideo1.mp4 -i inputVideo2.mp4 -filter_complex xfade=transition=slideup:duration=5:offset=0 slideupVideo.mp4

ffmpeg -i inputVideo1.mp4 -i inputVideo2.mp4 -filter_complex xfade=transition=slideleft:duration=5:offset=0 slideleftVideo.mp4

ffmpeg -i inputVideo1.mp4 -i inputVideo2.mp4 -filter_complex xfade=transition=slideright:duration=5:offset=0 sliderightVideo.mp4


ffmpeg -i inputVideo1.mp4 -i inputVideo2.mp4 -filter_complex xfade=transition=distance:duration=5:offset=0 distanceVideo.mp4


ffmpeg -i inputVideo1.mp4 -i inputVideo2.mp4 -filter_complex xfade=transition=diagtl:duration=5:offset=0 diagtlVideo.mp4
