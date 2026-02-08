namespace GuvenlikUI.Models{
    // Login formundan gelen veri
    public class LoginViewModel{
        public string Username {get; set;}
        public string Password {get; set;}
    }

    // Python'dan dönen Token cevabı
    public class TokenResponse {
        public string access_token {get; set;}
        public string token_type {get; set;}
        public string role {get; set;}
    }

    // Python'dan dönen Plaka verisi
    public class PlateModel  {
        public int id {get; set;}
        public string plate_number {get; set;}
        public string created_at {get; set;}
        public int user_id {get; set;}
    }
}