coverage run --branch --source=data,db,broker,config,const,util --omit=*/lib/* test
coverage xml -i -o coverage-reports/coverage.xml --include=./*.py --omit=./test
D:/sonar-scanner-4.6.2.2472-windows/bin/sonar-scanner.bat -Dsonar.login=%1