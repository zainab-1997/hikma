# Hikma Order Automation v1.0.0-rc1 release checklist

Complete this checklist in the target staging environment before approving production.

## Configuration and security

- [ ] Environment configured from the reviewed examples
- [ ] Environment file and all secrets protected with least-privilege permissions
- [ ] Repository and deployment artifacts independently scanned for real secrets
- [ ] Production CORS origins and allowed hosts explicitly configured
- [ ] Frontend API URL configured to the public HTTPS API origin
- [ ] HTTPS enabled with a valid certificate and HTTP redirected to HTTPS

## Data and recovery

- [ ] Source workbook hash recorded and matches `730edb4229048a7b7ff6b593749e7b507cfd547936fe7b306637869636f119c8`
- [ ] Database backup completed from a quiesced or SQLite-online-backup snapshot
- [ ] Generated files backed up with the matching database snapshot
- [ ] Source workbook and protected configuration included in the versioned backup set
- [ ] Restore drill completed
- [ ] Restored database integrity and historical downloads verified

## Services and delivery

- [ ] SMTP tested with controlled non-production recipients
- [ ] Email-disabled behavior verified
- [ ] Mocked or controlled SMTP failure verified without order/file loss
- [ ] Health liveness check passing
- [ ] Health readiness check passing
- [ ] Request ID returned and correlated with safe request logs
- [ ] SQLite deployment uses one backend worker

## Browser and workflow QA

- [ ] Real browser desktop test completed
- [ ] Real browser mobile test completed
- [ ] Global horizontal overflow checked
- [ ] Modal Escape, overlay close, focus entry, and focus restoration checked
- [ ] Keyboard-only navigation and visible focus checked
- [ ] Loading, empty, error, retry, success, and disabled states checked
- [ ] Arabic order test completed
- [ ] Mixed Arabic/English direction and long customer names checked
- [ ] Long order test completed
- [ ] Ambiguous-product and strength-conflict blocking checked
- [ ] Duplicate-product visibility checked
- [ ] Excel download and email-history presentation checked
- [ ] Analytics empty state and product-value limitation checked
- [ ] Email failure test completed

## Release control

- [ ] Full backend suite, frontend lint, and production build rerun from the release artifact
- [ ] Dependency vulnerability scans rerun and results reviewed
- [ ] Release notes reviewed
- [ ] Backup owner and rollback owner identified
- [ ] Release tag `v1.0.0-rc1` created
