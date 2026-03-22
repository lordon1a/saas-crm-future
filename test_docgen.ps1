# DocGen API PowerShell Test Script
# Kullanım: .\test_docgen.ps1

$BaseUrl = "http://localhost:5000"
$ApiUrl = "$BaseUrl/api/docgen"

Write-Host "======================================" -ForegroundColor Cyan
Write-Host "🧪 DocGen API Test (PowerShell)" -ForegroundColor Cyan
Write-Host "======================================" -ForegroundColor Cyan

# Session oluştur
$session = New-Object Microsoft.PowerShell.Commands.WebRequestSession

Write-Host ""
Write-Host "🔐 1. Login yapılıyor..." -ForegroundColor Yellow

try {
    $loginBody = @{
        email = "test@example.com"  # Kendi email'ini yaz
        password = "test123"  # Kendi şifreni yaz
    }
    
    $loginResponse = Invoke-WebRequest -Uri "$BaseUrl/login" `
        -Method POST `
        -Body $loginBody `
        -WebSession $session `
        -MaximumRedirection 0 `
        -ErrorAction SilentlyContinue
    
    Write-Host "✅ Login başarılı (Status: $($loginResponse.StatusCode))" -ForegroundColor Green
} catch {
    Write-Host "❌ Login başarısız: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "⚠️  Email ve şifreyi test_docgen.ps1 dosyasında güncelle" -ForegroundColor Yellow
    exit
}

Write-Host ""
Write-Host "📋 2. Template listesi getiriliyor..." -ForegroundColor Yellow

try {
    $templatesResponse = Invoke-RestMethod -Uri "$ApiUrl/templates" `
        -Method GET `
        -WebSession $session
    
    Write-Host "✅ Template listesi alındı" -ForegroundColor Green
    Write-Host ($templatesResponse | ConvertTo-Json -Depth 5)
} catch {
    Write-Host "❌ Hata: $($_.Exception.Message)" -ForegroundColor Red
}

Write-Host ""
Write-Host "📚 3. Oluşturulan dokümanlar getiriliyor..." -ForegroundColor Yellow

try {
    $documentsResponse = Invoke-RestMethod -Uri "$ApiUrl/documents" `
        -Method GET `
        -WebSession $session
    
    Write-Host "✅ Doküman listesi alındı" -ForegroundColor Green
    Write-Host ($documentsResponse | ConvertTo-Json -Depth 5)
} catch {
    Write-Host "❌ Hata: $($_.Exception.Message)" -ForegroundColor Red
}

Write-Host ""
Write-Host "======================================" -ForegroundColor Cyan
Write-Host "✅ Test tamamlandı" -ForegroundColor Green
Write-Host "======================================" -ForegroundColor Cyan
