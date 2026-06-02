FROM maven:3.9-eclipse-temurin-21 
WORKDIR /app
COPY . .
RUN mvn package -DskipTests 
CMD ["sh", "-c", "java -jar target/*.jar"]
