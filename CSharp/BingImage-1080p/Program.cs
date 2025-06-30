using System;
using System.IO;
using System.Net.Http;
using System.Net.Http.Headers;
using System.Threading.Tasks;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;

namespace BingImage
{
    class Program
    {
        static async Task Main(string[] args)
        {
            string apiUrl = "https://www.bing.com/HPImageArchive.aspx?format=js&idx=0&n=1";
            string savePath;

            // 处理用户输入路径
            if (args.Length == 0)
            {
                Console.WriteLine("请输入要保存的文件夹：");
                savePath = Console.ReadLine();
                if (string.IsNullOrEmpty(savePath))
                {
                    Console.WriteLine("路径无效，请重新运行程序并输入有效路径。");
                    return;
                }
            }
            else
            {
                savePath = args[0];
            }

            try
            {
                // 获取图片信息
                var (imageUrl, imageCopyright) = await GetBingImageInfoAsync(apiUrl);
                if (string.IsNullOrEmpty(imageUrl))
                {
                    Console.WriteLine("无法获取Bing每日一图的URL。");
                    return;
                }

                Console.WriteLine($"Bing每日一图的链接为：{imageUrl}");
                Console.WriteLine($"Bing每日一图的版权信息为：{imageCopyright ?? "无法获取"}");

                // 下载图片
                byte[] imageBytes = await DownloadImageAsync(imageUrl);
                string fileName = $"bing_pic_{DateTime.Now:yyyy-MM-dd}.jpg";
                string fullSavePath = Path.Combine(savePath, fileName);

                // 保存图片
                SaveImage(fullSavePath, imageBytes);
                Console.WriteLine($"Bing每日一图已保存到：{fullSavePath}");
            }
            catch (Exception ex)
            {
                Console.WriteLine($"发生错误：{ex.Message}");
            }
        }

        /// <summary>
        /// 异步获取Bing每日一图的信息
        /// </summary>
        /// <param name="apiUrl">Bing API的URL</param>
        /// <returns>图片URL和版权信息</returns>
        static async Task<(string? imageUrl, string? imageCopyright)> GetBingImageInfoAsync(string apiUrl)
        {
            using var client = new HttpClient();
            client.DefaultRequestHeaders.AcceptCharset.Add(new StringWithQualityHeaderValue("utf-8"));

            Console.WriteLine("正在访问Bing每日一图API接口......");

            HttpResponseMessage response = await client.GetAsync(apiUrl);
            response.EnsureSuccessStatusCode();
            string json = await response.Content.ReadAsStringAsync();
            JObject data = JsonConvert.DeserializeObject<JObject>(json) ?? throw new InvalidOperationException("JSON解析失败");

            JArray images = (JArray)data["images"];
            if (images == null || images.Count == 0)
            {
                return (null, null);
            }

            JObject firstImage = (JObject)images[0];
            string imageUrl = firstImage["url"]?.ToString();
            string imageCopyright = firstImage["copyright"]?.ToString();
            string fullImageUrl = imageUrl != null ? "https://www.bing.com" + imageUrl : null;

            return (fullImageUrl, imageCopyright);
        }

        /// <summary>
        /// 异步下载图片
        /// </summary>
        /// <param name="imageUrl">图片URL</param>
        /// <returns>图片的字节数组</returns>
        static async Task<byte[]> DownloadImageAsync(string imageUrl)
        {
            using var client = new HttpClient();
            return await client.GetByteArrayAsync(imageUrl);
        }

        /// <summary>
        /// 保存图片到指定路径
        /// </summary>
        /// <param name="path">保存路径</param>
        /// <param name="imageBytes">图片字节数组</param>
        static void SaveImage(string path, byte[] imageBytes)
        {
            try
            {
                Directory.CreateDirectory(Path.GetDirectoryName(path)!);
                File.WriteAllBytes(path, imageBytes);
            }
            catch (Exception ex)
            {
                throw new InvalidOperationException($"保存图片失败：{ex.Message}", ex);
            }
        }
    }
}