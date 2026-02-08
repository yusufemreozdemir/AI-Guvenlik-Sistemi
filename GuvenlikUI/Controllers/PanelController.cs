using Microsoft.AspNetCore.Mvc;
using GuvenlikUI.Models;
using Newtonsoft.Json;
using System.Net.Http.Headers;

namespace GuvenlikUI.Controllers {
    public class PanelController : Controller {
        private readonly HttpClient _httpClient;
        private readonly string _pythonApiUrl = "http://localhost:8000";

        public PanelController(){
            _httpClient = new HttpClient();
        }

        // Token ve veri çekme
        private async Task<List<PlateModel>> GetPlatesFromApi() {

            var token = HttpContext.Session.GetString("JWToken");
            if (string.IsNullOrEmpty(token)) return null;

            _httpClient.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("Bearer", token);
            var response = await _httpClient.GetAsync($"{_pythonApiUrl}/plates/");
            
            if (response.IsSuccessStatusCode){
                var jsonString = await response.Content.ReadAsStringAsync();
                return JsonConvert.DeserializeObject<List<PlateModel>>(jsonString);
            }
            return new List<PlateModel>();
        }

        // Site sakini paneli
        public async Task<IActionResult> ResidentPanel(){

            if (HttpContext.Session.GetString("UserRole") == "Security") 
                return RedirectToAction("SecurityPanel");

            var plates = await GetPlatesFromApi();
            if (plates == null) return RedirectToAction("Login", "Account");
            
            return View(plates);
        }

        // Güvenlik paneli
        public async Task<IActionResult> SecurityPanel(){
            var role = HttpContext.Session.GetString("UserRole");
            // Eğer normal kullanıcı girmeye çalışırsa engelle
            if (role != "Security" && role != "Admin") 
                return RedirectToAction("ResidentPanel");

            var plates = await GetPlatesFromApi();
            if (plates == null) return RedirectToAction("Login", "Account");

            return View(plates);
        }

        // Plaka ekleme fonksiyonu
        [HttpPost]
        public async Task<IActionResult> AddPlate(string plateNumber, string returnUrl) {
            var token = HttpContext.Session.GetString("JWToken");
            _httpClient.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("Bearer", token);

            var newPlate = new { plate_number = plateNumber };
            var content = new StringContent(JsonConvert.SerializeObject(newPlate), System.Text.Encoding.UTF8, "application/json");

            var response = await _httpClient.PostAsync($"{_pythonApiUrl}/plates/", content);

            if (response.IsSuccessStatusCode) TempData["Message"] = "Plaka eklendi.";
            else TempData["Error"] = "Hata oluştu.";

            return Redirect(returnUrl); // Hangi sayfadan geldiyse oraya geri dön
        }

        // Ana dashboard
        public IActionResult AdminDashboard(){
            // Sadece admin ve security girebilsin
            var role = HttpContext.Session.GetString("UserRole");
            if (role != "Admin" && role != "Security") return RedirectToAction("Login", "Account");

            return View();
        }
        

        // Geçmiş logları görüntüleme
        public async Task<IActionResult> AdminLogs() {

            var logs = new List<AdminLogModel>();
            // Python API'den veriyi çek
            var token = HttpContext.Session.GetString("JWToken");
                _httpClient.DefaultRequestHeaders.Authorization = new System.Net.Http.Headers.AuthenticationHeaderValue("Bearer", token);
                
                var response = await _httpClient.GetAsync($"{_pythonApiUrl}/admin/logs");

                if (response.IsSuccessStatusCode){
                    var jsonString = await response.Content.ReadAsStringAsync();
                    logs = JsonConvert.DeserializeObject<List<AdminLogModel>>(jsonString);
                }

            return View(logs);
        }



        // Tüm plakaları ve ekleyen kullanıcıları görüntüleme
        public async Task<IActionResult> AdminPlates(){
            var plates = new List<AdminPlateModel>();
            var token = HttpContext.Session.GetString("JWToken");
            _httpClient.DefaultRequestHeaders.Authorization = new System.Net.Http.Headers.AuthenticationHeaderValue("Bearer", token);

            var response = await _httpClient.GetAsync($"{_pythonApiUrl}/admin/plates");

            if (response.IsSuccessStatusCode) {
                 var jsonString = await response.Content.ReadAsStringAsync();
                plates = JsonConvert.DeserializeObject<List<AdminPlateModel>>(jsonString);
            }
            return View(plates);
        }
    }
}