# tf2-model-g
Model G implemented in Tensorflow v2

## Installation
This code is intented to run on Google Cloud on the Deep Learning VM available in the Marketplace.
To install any dependencies not already included in the VM run
```bash
pip3 install -r requirements.txt
```

## Local development

### Requirements
- python3
```bash
sudo apt install python3
```
- pip3
```bash
sudo apt update -y
sudo apt install python3-pip -y
```
- [Tensorflow 2](https://www.tensorflow.org/install)
```bash
pip3 install tensorflow
```
- Additional dependencies
```bash
pip3 install -r requirements.txt
```
run code example:
```bash
python3 render_video.py ~/tf2-model-g/nucleation_and_motion_in_fluid_2D.mp4 --params params/nucleation_and_motion_in_fluid_2D.yaml
```
run with plotting facility
```bash
pip3 install matplotlib
```

Install ffmpeg:
```bash
sudo add-apt-repository ppa:mc3man/trusty-media
sudo apt-get update
sudo apt-get install ffmpeg
```
See --- [How to install ffmpeg for ubuntu using command line?](https://stackoverflow.com/questions/42589892/how-to-install-ffmpeg-for-ubuntu-using-command-line)


Programming text/debug editor:

- [Visual Studio Code](https://code.visualstudio.com/)

Install scipy:
```bash
sudo apt-get install python-pip  
sudo pip install numpy scipy
```
>>>>>>> c470e6c43e97d316bb2cf56bb5eaa00b23bee8a8
