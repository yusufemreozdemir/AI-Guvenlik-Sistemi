using Microsoft.AspNetCore.Mvc;
using GuvenlikUI.Models;
using Newtonsoft.Json;

namespace GuvenlikUI.Controllers{
    public class AccountController : Controller {
        private readonly HttpClient _httpClient;
        private readonly string _pythonApiUrl = "http://localhost:8000";

        public AccountController(){
            _httpClient = new HttpClient();
        }

        [HttpGet]
        public IActionResult Login() {
            return View();
        }

        [HttpPost]
        public async Task<IActionResult> Login(LoginViewModel model) {
            try {
                var content = new FormUrlEncodedContent(new[]{
                    new KeyValuePair<string, string>("username", model.Username),
                    new KeyValuePair<string, string>("password", model.Password)
                });

                var response = await _httpClient.PostAsync($"{_pythonApiUrl}/login", content);

                if (response.IsSuccessStatusCode) {
                    var jsonString = await response.Content.ReadAsStringAsync();
                    var tokenData = JsonConvert.DeserializeObject<TokenResponse>(jsonString);

                    if(tokenData != null && !string.IsNullOrEmpty(tokenData.access_token)){
                        // Session'a verileri kaydet
                        HttpContext.Session.SetString("JWToken", tokenData.access_token);
                        HttpContext.Session.SetString("Username", model.Username);
                        HttpContext.Session.SetString("UserRole", tokenData.role);
                        
                        //Yönlendirmeler
                        if (tokenData.role == "Admin")    
                            return RedirectToAction("AdminDashboard", "Panel");
                        
                        else if (tokenData.role == "Security")
                            return RedirectToAction("SecurityPanel", "Panel");
                        
                        else
                            return RedirectToAction("ResidentPanel", "Panel");
                    }
                }
            }
            catch(Exception ex){
                ViewBag.Error = "Bağlantı Hatası: " + ex.Message;
                return View();
            }

            ViewBag.Error = "Hatalı giriş bilgileri.";
            return View();
        }



        public IActionResult Logout(){
            HttpContext.Session.Clear();
            return RedirectToAction("Login");
        }
    }
}