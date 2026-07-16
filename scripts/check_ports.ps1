param([int]$Port = 3800)
$ErrorActionPreference = "Stop"

$Listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, $Port)
try {
    $Listener.Start()
    Write-Host "Port $Port is available."
}
catch {
    $Owner = & ss --numeric --tcp --listening --processes "sport = :$Port" 2>$null | Out-String
    Write-Error "Port $Port is already in use. SpeechShift will not select a random port.`n$Owner"
}

finally {
    $Listener.Stop()
}
