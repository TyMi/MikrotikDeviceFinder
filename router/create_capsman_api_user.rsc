# =============================================================================
# MikrotikDeviceFinder - Read-only API-User fuer den CAPsMAN-Controller
# Auszufuehren auf dem RouterOS-7.x-Geraet, das die CAPsMAN-Rolle traegt
# (getestet mit dem neuen "wifi"-Paket / wifiwave2, nicht dem alten caps-man).
#
# Vor dem Ausfuehren anpassen:
#   - APP_SERVER_IP : IP des Servers, der die Web-App hostet
#   - STRONG_PASSWORD : durch ein eigenes, starkes Passwort ersetzen
# =============================================================================

# 1) Dedizierte Gruppe mit minimalen Rechten anlegen.
#    "read"     -> darf Konfiguration/Status lesen (z.B. Registration-Table)
#    "web"      -> darf ueber HTTP(S)/Webfig-Dienst zugreifen (REST-API laeuft darueber)
#    "api"      -> darf die klassische API-Schnittstelle nutzen
#    "rest-api" -> eigene, von "api"/"web" getrennte Policy speziell fuer die
#                  REST-API. OHNE diese Policy antwortet RouterOS mit einem
#                  generischen 401 Unauthorized, obwohl User/Passwort korrekt
#                  sind - sieht wie ein falsches Passwort aus, ist aber ein
#                  Rechteproblem. (alle drei - web/api/rest-api - zu setzen
#                  schadet bei einem dedizierten Read-only-Account nicht)
#    Alles andere (write, policy, test, ssh, telnet, ftp, winbox, password, sniff,
#    sensitive, romon, dude, tikapp, local, reboot) bleibt deaktiviert.
/user group
add name=capsman-readonly policy=read,web,api,rest-api comment="MikrotikDeviceFinder: read-only fuer CAPsMAN-Abfrage"

# 2) User anlegen und auf die IP des App-Servers beschraenken.
#    "address" erlaubt Login nur von dieser IP/diesem Subnetz - unabhaengig davon,
#    von wo sonst noch auf den Router zugegriffen wird.
/user
add name=capsman-api group=capsman-readonly address=APP_SERVER_IP/32 password="STRONG_PASSWORD" comment="MikrotikDeviceFinder web app - read only"

# 3) Sicherstellen, dass der Dienst fuer die REST-API aktiv ist.
#    www-ssl (HTTPS) wird empfohlen. Dafuer muss dem Dienst ein Zertifikat
#    zugewiesen sein - siehe Hinweis unten.
/ip service
set www-ssl disabled=no
print where name=www-ssl

# =============================================================================
# Hinweise:
#
# a) HTTPS-Zertifikat fuer www-ssl:
#    "key-usage=tls-server" allein ist NICHT selbst-signierbar (`sign` schlaegt
#    mit "failure: CA not found" fehl). Erst eine eigene CA anlegen und
#    selbst signieren, danach das eigentliche Zertifikat DAMIT signieren:
#
#    /certificate
#    add name=local-ca common-name=MikrotikDeviceFinder-CA key-usage=key-cert-sign,crl-sign days-valid=3650
#    sign local-ca
#
#    add name=rest-api-cert common-name=capsman.local key-usage=tls-server days-valid=365
#    sign rest-api-cert ca=local-ca
#
#    /ip service set www-ssl certificate=rest-api-cert
#
#    Ohne Zertifikat startet www-ssl nicht korrekt bzw. die REST-API ist nur
#    ueber unverschluesseltes HTTP (www) erreichbar.
#
# b) Test von der Kommandozeile aus (vom App-Server, curl -k wegen self-signed cert).
#    Pfad haengt vom WLAN-Paket ab:
#    - Neues "wifi"-Paket (wifiwave2, RouterOS >= 7.13 ueblich):
#
#      curl -k -u capsman-api:STRONG_PASSWORD \
#        https://<CAPSMAN-IP>/rest/interface/wifi/registration-table
#
#    - Altes "caps-man"-Paket:
#
#      curl -k -u capsman-api:STRONG_PASSWORD \
#        https://<CAPSMAN-IP>/rest/caps-man/registration-table
#
#    Im Zweifel einfach beide testen - der falsche Pfad liefert einen 400/404,
#    keinen Auth-Fehler.
#
# c) Passwort NICHT im Klartext in Skripten/Git ablegen. Dieses .rsc-File ist ein
#    Template - das echte Passwort direkt am Router setzen oder per Winbox/Webfig
#    manuell vergeben statt es hier fest einzutragen.
# =============================================================================
