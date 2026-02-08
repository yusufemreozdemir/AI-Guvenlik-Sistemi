var builder = WebApplication.CreateBuilder(args);

// Servisleri ekle
builder.Services.AddControllersWithViews();
builder.Services.AddSession(); // <--- SESSION EKLENDİ

var app = builder.Build();

if (!app.Environment.IsDevelopment()){
    app.UseExceptionHandler("/Home/Error");
    app.UseHsts();
}

app.UseHttpsRedirection();
app.UseStaticFiles();

app.UseRouting();

app.UseSession(); // <--- SESSION AKTİF EDİLDİ (UseRouting'den sonra olmalı)
app.UseAuthorization();

// Varsayılan açılış sayfasını Login yaptık
app.MapControllerRoute(
    name: "default",
    pattern: "{controller=Account}/{action=Login}/{id?}");

app.Run();