## Install Chromedriver in WSL


https://www.gregbrisebois.com/posts/chromedriver-in-wsl2/

### Initial install
```
sudo apt-get update
sudo apt-get install -y curl unzip xvfb libxi6 libgconf-2-4
```

```
wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
sudo apt install ./google-chrome-stable_current_amd64.deb
```

Check
```
google-chrome --version
```


### Install chromedriver

Check the driver number and install

Example
```
wget https://storage.googleapis.com/chrome-for-testing-public/138.0.7204.183/linux64/chromedriver-linux64.zip
unzip chromedriver-linux64.zip
cd chromedriver-linux64/
```


Install

```
sudo mv chromedriver /usr/bin/chromedriver
sudo chown root:root /usr/bin/chromedriver
sudo chmod +x /usr/bin/chromedriver
```

Check

```
chromedriver --version
```