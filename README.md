因为本人比较喜欢`Bing`的每日一图，在树莓派4b上也使用[1panel](https://github.com/1Panel-dev/1Panel)部署了每天下载的脚本，`1080p`与`4k`分别下载，目前已经正常运行一年有余，现在拿出来进行分享
本项目有三个部分组成，`Csharp`，`Python`和`Check_shell`，第一个是编译为单个可执行文件，配合定时任务在本地获取图片，第二个是在发现计划任务执行错误或者忘记执行时，补漏用，最后一个是在树莓派上直接运行的脚本，检查是否存在遗漏
## CSharp
本部分采用官方api获取下载链接 [官方接口](https://www.bing.com/HPImageArchive.aspx?format=js&idx=0&n=1) ，使用了第三方库`Newtonsoft.Json`，编译前请下载好
```shell
dotnet add package Newtonsoft.Json
```
本部分下载分为`1080p`和`4k`，使用方法一样，两个项目采用命令行在控制台创建，要编译请自行下载`dotnet`， [.Net下载](https://dotnet.microsoft.com/en-us/download)  
项目创建方法为在命令行直接创建
```shell
donet new console -n BingImage
```
本项目没有使用`IDE`，故没有`.sln`文件，如果需要修改程序，请直接修改`Program.cs`文件，注释还算比较完整
### 编译
如果需要编译为单个可执行文件，编译目标为`Windows`为例，请在`BingPic\CSharp\BingImage-1080p`文件夹或者`BingPic\CSharp\BingImage-4k`文件夹内打开命令行，并输入
```shell
dotnet publish -r win-x64 -c Release --self-contained
```
如果要编译为其他平台的可执行文件，可以把`win-x64`进行替换，例如给树莓派4b编译，可以替换为`linux-arm64`  
编译完成后，可以在`bin`文件夹内的`Publish`里面找到单个的可执行文件
### 使用说明
该程序可以直接运行，在命令行里面输入保存路径，例如：
![image](https://github.com/user-attachments/assets/5589f0a2-1c30-422b-8e90-dd72ba33c81e)
也可以在运行时，在后面加上保存路径作为参数，例如：
![image](https://github.com/user-attachments/assets/b4155301-d51f-4527-8551-6cf3742d1c4b)

## Python
本部分采用第三方api实现 [第三方接口网站](https://bing.ee123.net/)
程序使用了第三方库`requests`，如果需要运行，请先下载第三方库的依赖
```shell
pip install requests
```
### API说明
> 获取当日图像 https://bing.ee123.net/img/ (1080P图像) https://bing.ee123.net/img/4k (4k图像)  \
> 随机图像 https://bing.ee123.net/img/rand \
> 可请求分辨率：UHD , 1920x1200 , 1920x1080 , 1366x768 , 1280x768 ,1024x768 , 800x600 , 800x480 , 768x1280 ,720x1280 , 640x480 , 480x800 , 400x240 , 320x240 , 240x320
> > 参数说明：https://bing.ee123.net/img/?date=20250630&size=1920x1080&imgtype=jpg&type=json \
> > date=20250630  指定日期（2010/01/01到现在），随机图像API时无效，可省略 \
> > size=1920x1080 | w1600 | h900  指定图像分辨率、宽度及高度，设定一项即可，可省略 \
> > imgtype=jpg  支持格式为jpg和webp，默认返回jpg图像，可省略 \
> > type=json  返回JSON格式数据，为空则直接返回图像

### 使用说明
本部分分为`Batch`和`Single`，`Batch`是批量下载，`Single`为指定日期单个下载，两个的使用方法类似
对于批量下载，使用时请自行修改`start_date`和`end_date`，运行时，将会在程序运行的目录创建以年份为单位的文件夹，并将对应年份的图片放进去 
![image](https://github.com/user-attachments/assets/4852aa29-098f-4129-815d-20d2e2bf8250)  
对于单个文件，使用时请自行修改 `date`，运行时将会把下载的图片自动放在程序运行的目录中  
![image](https://github.com/user-attachments/assets/8a5be56a-74e8-4b44-8fce-f973e7be9168)

> ps:由于使用的是第三方api，在实际使用时发现，`4k`图片在`2019-05-09`之前，并没有达到4k分辨率，如对`2019-05-09`之前的4k图片有需要，请寻找其他第三方api

## Check_shell
此部分是基于`zsh`编写的脚本，使用正则表达式匹配当前文件夹内的图片文件名，并打印出缺失的图片名称，请根据`1080p`和`4k`的文件夹，分别使用脚本，具体有两种使用方式 \
第一个是直接运行该脚本，它会检查出今年从`01-01`到运行脚本的日期之间是否有图片遗漏，如果有，则会打印出遗漏的图片名称，没有，则会打印出`no pic`
第二个是在脚本后面跟上年份，例如：
```shell
./check_pic.sh 2023 
```
则该脚本会打印出2023年缺失的图片名称，如果没有，也会打印出`no pic`