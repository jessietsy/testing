FROM maven:3.9-eclipse-temurin-17
WORKDIR /app
COPY . .
RUN mvn package -DskipTests -q
CMD ["sh", "-c", "java -jar target/*.jar"]
