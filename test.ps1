$headers = @{"Content-Type" = "application/json"}
$body = '{"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"}'
try {
    $response = Invoke-RestMethod -Uri http://localhost:8787/api/download -Method POST -Headers $headers -Body $body
    Write-Host "Success:"
    $response | ConvertTo-Json
} catch {
    Write-Host "Error:"
    Write-Host $_.Exception.Message
}