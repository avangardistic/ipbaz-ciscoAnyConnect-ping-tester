# diagnose.ps1
Write-Host "=== Adapters ==="
Get-NetAdapter | Where-Object { $_.InterfaceDescription -match 'Wintun|TAP' } |
    Format-Table Name, Status, ifIndex, InterfaceDescription

Write-Host "`n=== Default Routes (0.0.0.0/0) ==="
Get-NetRoute -DestinationPrefix "0.0.0.0/0" |
    Format-Table InterfaceAlias, NextHop, RouteMetric, ifIndex

Write-Host "`n=== DNS Servers ==="
Get-DnsClientServerAddress -AddressFamily IPv4 |
    Where-Object { $_.ServerAddresses } |
    Format-Table InterfaceAlias, ServerAddresses

Write-Host "`n=== Interface Metrics ==="
Get-NetIPInterface -AddressFamily IPv4 |
    Sort-Object InterfaceMetric |
    Format-Table InterfaceAlias, InterfaceMetric

Write-Host "`n=== Test DNS resolution ==="
Resolve-DnsName www.youtube.com -ErrorAction SilentlyContinue |
    Select-Object -First 3

Write-Host "`n=== Test TCP to YouTube ==="
Test-NetConnection www.youtube.com -Port 443 -InformationLevel Quiet