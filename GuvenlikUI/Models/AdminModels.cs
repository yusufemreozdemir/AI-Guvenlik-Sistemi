namespace GuvenlikUI.Models {
    public class AdminLogModel {
        public int id {get; set;}
        public string plate_number {get; set;}
        public bool access_status {get; set; }
        public string vlm_description {get; set;}
        public DateTime timestamp {get; set;}
        public string related_user {get; set;} // Python'dan gelen kullanıcı adı
    }

    public class AdminPlateModel {
        public int id {get; set;}
        public string plate_number {get; set;}
        public DateTime created_at {get; set;}
        public string owner_username {get; set;} // Plakayı kim ekledi?
    }
}