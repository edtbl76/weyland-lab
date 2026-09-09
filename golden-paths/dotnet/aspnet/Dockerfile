# Golden path .NET / ASP.NET Core. Multi-stage: dotnet SDK build → aspnet runtime. buildkit → registry.weyland.lab/golden-dotnet-aspnet.
FROM mcr.microsoft.com/dotnet/sdk:8.0 AS build
WORKDIR /src
COPY App/App.csproj ./App/
RUN dotnet restore App/App.csproj
COPY App/Program.cs ./App/
RUN dotnet publish App/App.csproj -c Release -o /app --no-restore
FROM mcr.microsoft.com/dotnet/aspnet:8.0
WORKDIR /app
RUN useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin appuser \
 && apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*
COPY --from=build /app ./
COPY smoke.sh ./
USER 10001
EXPOSE 8080
# .NET 8 aspnet images default ASPNETCORE_URLS to http://+:8080, so the app binds :8080.
ENTRYPOINT ["dotnet", "App.dll"]
