# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability in WiFi Tracker, please report it responsibly.

**Do NOT open a public GitHub issue for security vulnerabilities.**

Instead, please email the maintainers directly with:

- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if any)

## Response Timeline

- **Acknowledgment**: Within 48 hours
- **Initial assessment**: Within 1 week
- **Fix or mitigation**: Depends on severity, typically within 2 weeks for critical issues

## Security Features

WiFi Tracker includes several security features:

- **MITM/Rogue Gateway Detection**: Monitors for unknown gateway MAC addresses and alerts when a new gateway is detected on your network
- **Gateway Trust System**: Users can explicitly trust known gateways; unknown ones trigger notifications
- **Network Monitoring**: Real-time monitoring of network connections and usage patterns

## Scope

Security issues include:

- Remote code execution
- Privilege escalation
- Data exposure (usage data, network credentials)
- Bypass of security features (MITM detection, gateway trust)
- Dependency vulnerabilities

## Out of Scope

- Denial of service against the tracker itself
- Issues requiring physical access to the machine
- Social engineering attacks

## Best Practices for Users

1. Run the daemon with minimal privileges (user-level systemd service)
2. Keep dependencies updated
3. Review trusted gateways periodically: `wifi-tracker trusted-gateways`
4. Use `--quiet` mode in untrusted environments to avoid notification-based attacks
