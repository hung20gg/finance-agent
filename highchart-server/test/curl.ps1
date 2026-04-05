param(
    [string]$ChartFile = "chart.js",
    [string]$OutputFile = "chart.png",
    [string]$ServerUrl = "http://localhost:3000/render"
)

# Convert curl command to PowerShell
# Original: curl -X POST http://localhost:3000/render -H "Content-Type: text/plain" --data-binary @chart.js --output chart.png

try {
    # Read the chart.js file content
    $chartContent = Get-Content -Path $ChartFile -Raw -Encoding UTF8

    # Make the POST request
    $response = Invoke-WebRequest -Uri $ServerUrl -Method POST -ContentType "text/plain" -Body $chartContent -OutFile $OutputFile

    Write-Host "Chart rendered successfully. Output saved to: $OutputFile"
}
catch {
    Write-Error "Failed to render chart: $_"
    exit 1
}